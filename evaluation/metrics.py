"""Cost, latency and length summaries across saved runs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config

NUMERIC_COLUMNS = [
    "latency_seconds",
    "sequential_latency_seconds",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "word_count",
    "token_count",
    "llm_calls",
]


def load_runs_csv(path: Path | None = None) -> pd.DataFrame:
    """Load the flat runs CSV as a DataFrame (empty frame if it does not exist)."""
    csv_path = path or config.RUNS_CSV
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def summarise_by_system(df: pd.DataFrame, experiment: str | None = None) -> pd.DataFrame:
    """Mean/SD per system for latency, tokens, cost and length, plus budget compliance.

    Args:
        df: Output of :func:`load_runs_csv`.
        experiment: Optional filter on the ``experiment`` column (e.g. "main").
    """
    if df.empty:
        return pd.DataFrame()
    if experiment:
        df = df[df["experiment"] == experiment]
    agg = {col: ["mean", "std"] for col in NUMERIC_COLUMNS if col in df}
    summary = df.groupby("system_type").agg(agg)
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]
    summary["n_runs"] = df.groupby("system_type").size()
    if "within_length_budget" in df:
        summary["share_within_length_budget"] = (
            df.assign(w=df["within_length_budget"].astype(str).str.lower() == "true")
            .groupby("system_type")["w"]
            .mean()
        )
    return summary.round(4)
