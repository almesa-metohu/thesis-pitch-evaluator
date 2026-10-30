"""Derive thesis reporting statistics from committed experiment outputs.

Produces aggregate stability means/SDs across all 30 pairwise comparisons per
system and mean/SD sequential latency across the six main runs per system.
Uses sample standard deviation (n-1).
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABILITY_PATH = ROOT / "thesis_results" / "stability" / "stability_results.json"
MAIN_PATH = ROOT / "thesis_results" / "main_runs_summary.csv"
OUTPUT_PATH = ROOT / "thesis_results" / "derived_reporting_statistics.csv"

METRICS = [
    ("risk_overlap", "risk_overlap"),
    ("recommendation_overlap", "recommendation_overlap"),
    ("lexical_jaccard", "lexical_jaccard"),
    ("section_jaccard_mean", "section_jaccard_mean"),
    ("sequence_ratio", "sequence_ratio"),
]


def pooled_mean_sd(groups: list[tuple[float, float, int]]) -> tuple[float, float, int]:
    n_total = sum(n for _, _, n in groups)
    mean = sum(mean * n for mean, _, n in groups) / n_total
    ss = sum(
        (n - 1) * (sd ** 2) + n * ((group_mean - mean) ** 2)
        for group_mean, sd, n in groups
    )
    sample_sd = math.sqrt(ss / (n_total - 1))
    return mean, sample_sd, n_total


def sample_mean_sd(values: list[float]) -> tuple[float, float, int]:
    n = len(values)
    mean = sum(values) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))
    return mean, sd, n


def main() -> None:
    stability = json.loads(STABILITY_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []

    for system in ("single", "multi"):
        system_results = [r for r in stability["results"] if r["system_type"] == system]
        for output_name, json_name in METRICS:
            groups = [
                (
                    float(r["agreement"][json_name]["mean"]),
                    float(r["agreement"][json_name]["sd"]),
                    int(r["agreement"][json_name]["n_pairs"]),
                )
                for r in system_results
            ]
            mean, sd, n = pooled_mean_sd(groups)
            rows.append(
                {
                    "statistic": output_name,
                    "system": system,
                    "mean": f"{mean:.4f}",
                    "sd": f"{sd:.4f}",
                    "n": n,
                    "unit_or_scale": "0-1",
                    "source": "stability_results.json pooled across 3 pitches x 10 run-pairs",
                }
            )

    with MAIN_PATH.open(newline="", encoding="utf-8") as f:
        main_rows = list(csv.DictReader(f))

    for system in ("single", "multi"):
        values = [
            float(r["sequential_latency_seconds"])
            for r in main_rows
            if r["system_type"] == system and r["experiment"] == "main"
        ]
        mean, sd, n = sample_mean_sd(values)
        rows.append(
            {
                "statistic": "sequential_latency_seconds",
                "system": system,
                "mean": f"{mean:.3f}",
                "sd": f"{sd:.3f}",
                "n": n,
                "unit_or_scale": "seconds",
                "source": "main_runs_summary.csv",
            }
        )

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "statistic",
                "system",
                "mean",
                "sd",
                "n",
                "unit_or_scale",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
