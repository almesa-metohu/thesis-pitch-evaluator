"""Statistical analysis of reviewer ratings plus cost/latency comparison.

Paired design: each (reviewer, pitch) rates BOTH systems, so ratings are paired
by reviewer x pitch x criterion and compared with the Wilcoxon signed-rank test
(scipy.stats.wilcoxon). Zero differences are dropped by scipy's default
``zero_method="wilcox"``; the number of informative pairs is reported.

Example:
    python -m evaluation.analyse_results --ratings data/ratings/ratings.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

import config
from evaluation.metrics import load_runs_csv, summarise_by_system
from evaluation.rubric import DOMAINS, depth_columns

CRITERION_COLUMNS = ["specificity", *depth_columns(), "depth_overall", "clarity", "usefulness"]


def load_ratings(path: Path, key_path: Path | None = None) -> pd.DataFrame:
    """Load reviewer ratings and resolve ``system_type`` via the blinding key if needed."""
    df = pd.read_csv(path, dtype={"report_label": str, "system_type": str})
    key_file = key_path or (config.RATINGS_DIR / "blinding_key.csv")
    if ("system_type" not in df or df["system_type"].isna().all() or (df["system_type"] == "").all()):
        if not key_file.exists():
            raise FileNotFoundError(f"Ratings lack system_type and no blinding key at {key_file}")
        key = pd.read_csv(key_file, dtype=str)[["pitch_id", "report_label", "system_type"]]
        df = df.drop(columns=["system_type"], errors="ignore").merge(key, on=["pitch_id", "report_label"], how="left")
    if df["system_type"].isna().any():
        bad = df[df["system_type"].isna()][["pitch_id", "report_label"]].drop_duplicates()
        raise ValueError(f"Could not resolve system_type for: {bad.to_dict('records')}")
    for col in ["specificity", *depth_columns(), "clarity", "usefulness"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["depth_overall"] = df[depth_columns()].mean(axis=1)
    return df


def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Mean, median, SD and IQR per criterion and system."""
    rows = []
    for criterion in CRITERION_COLUMNS:
        for system, grp in df.groupby("system_type"):
            vals = grp[criterion].dropna()
            if vals.empty:
                continue
            q1, q3 = vals.quantile([0.25, 0.75])
            rows.append({"criterion": criterion, "system_type": system, "n": len(vals), "mean": vals.mean(), "median": vals.median(), "sd": vals.std(ddof=1) if len(vals) > 1 else 0.0, "iqr": q3 - q1})
    return pd.DataFrame(rows).round(3)


def paired_frame(df: pd.DataFrame, criterion: str) -> pd.DataFrame:
    """Wide frame with one row per (reviewer, pitch) and columns single / multi."""
    wide = df.pivot_table(index=["reviewer_id", "pitch_id"], columns="system_type", values=criterion, aggfunc="mean")
    return wide.dropna(subset=list(config.SYSTEM_TYPES))


def wilcoxon_tests(df: pd.DataFrame) -> pd.DataFrame:
    """Paired Wilcoxon signed-rank test per criterion (multi minus single)."""
    rows = []
    for criterion in CRITERION_COLUMNS:
        wide = paired_frame(df, criterion)
        diff = (wide["multi"] - wide["single"]).to_numpy(dtype=float)
        n_pairs = len(diff)
        n_nonzero = int(np.count_nonzero(diff))
        row = {"criterion": criterion, "n_pairs": n_pairs, "n_nonzero_pairs": n_nonzero, "median_single": float(np.median(wide["single"])) if n_pairs else np.nan, "median_multi": float(np.median(wide["multi"])) if n_pairs else np.nan, "median_difference": float(np.median(diff)) if n_pairs else np.nan, "mean_difference": float(np.mean(diff)) if n_pairs else np.nan, "statistic": np.nan, "p_value": np.nan, "note": ""}
        if n_nonzero == 0:
            row["note"] = "all paired differences are zero; test undefined"
        elif n_pairs < 5:
            row["note"] = "fewer than 5 pairs; p-value not meaningful"
        if n_nonzero > 0:
            try:
                res = stats.wilcoxon(wide["multi"], wide["single"], zero_method="wilcox", alternative="two-sided")
                row["statistic"], row["p_value"] = float(res.statistic), float(res.pvalue)
            except ValueError as exc:
                row["note"] = f"wilcoxon failed: {exc}"
        rows.append(row)
    return pd.DataFrame(rows).round(4)


def make_charts(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    """Boxplots per criterion (single vs multi) and a paired-difference chart."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths = []
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    for ax, criterion in zip(axes.flat, CRITERION_COLUMNS):
        data = [df.loc[df["system_type"] == s, criterion].dropna() for s in config.SYSTEM_TYPES]
        ax.boxplot(data, tick_labels=list(config.SYSTEM_TYPES))
        ax.set_title(criterion)
        ax.set_ylim(0, 5.5)
    fig.suptitle("Reviewer ratings by system")
    fig.tight_layout()
    p = out_dir / "ratings_boxplots.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)

    fig, ax = plt.subplots(figsize=(9, 4))
    diffs = [(paired_frame(df, c)["multi"] - paired_frame(df, c)["single"]).to_numpy() for c in CRITERION_COLUMNS]
    ax.axhline(0, color="grey", linewidth=1)
    ax.boxplot(diffs, tick_labels=CRITERION_COLUMNS)
    ax.set_ylabel("multi minus single")
    ax.set_title("Paired differences per criterion")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = out_dir / "paired_differences.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths.append(p)
    return paths


def cost_latency_summary(experiment: str | None) -> pd.DataFrame:
    """Average latency, cost and tokens per system from the runs log."""
    return summarise_by_system(load_runs_csv(), experiment)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratings", default=str(config.RATINGS_DIR / "ratings.csv"))
    parser.add_argument("--key", default=None, help="Blinding key CSV (default: data/ratings/blinding_key.csv)")
    parser.add_argument("--experiment", default="main", help="Experiment label for the cost/latency summary")
    parser.add_argument("--out-dir", default=str(config.RATINGS_DIR / "analysis"))
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_ratings(Path(args.ratings), Path(args.key) if args.key else None)

    desc = descriptive_stats(df)
    tests = wilcoxon_tests(df)
    desc.to_csv(out_dir / "descriptive_stats.csv", index=False)
    tests.to_csv(out_dir / "wilcoxon_tests.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n=== Descriptive statistics ===")
    print(desc.to_string(index=False))
    print("\n=== Wilcoxon signed-rank tests (paired by reviewer x pitch; multi minus single) ===")
    print(tests.to_string(index=False))
    print("\nInterpretation note: p-values are reported as computed; with small samples and multiple criteria, treat them as indicative, not conclusive.")

    cost = cost_latency_summary(args.experiment)
    if not cost.empty:
        cost.to_csv(out_dir / "cost_latency_summary.csv")
        cols = [c for c in ["n_runs", "latency_seconds_mean", "sequential_latency_seconds_mean", "total_tokens_mean", "estimated_cost_usd_mean", "word_count_mean", "share_within_length_budget"] if c in cost]
        print(f"\n=== Cost and latency (experiment='{args.experiment}') ===")
        print(cost[cols].to_string())
    else:
        print(f"\nNo runs with experiment='{args.experiment}' in {config.RUNS_CSV}; cost summary skipped.")

    if not args.no_charts:
        for p in make_charts(df, out_dir):
            print(f"chart: {p}")
    (out_dir / "analysis_meta.json").write_text(json.dumps({"ratings_file": args.ratings, "n_rows": len(df), "n_reviewers": int(df["reviewer_id"].nunique()), "n_pitches": int(df["pitch_id"].nunique()), "settings": config.generation_settings()}, indent=2), encoding="utf-8")
    print(f"\nTables and charts written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
