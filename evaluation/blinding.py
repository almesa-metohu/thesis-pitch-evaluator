"""Export anonymised (blinded) reports and rating templates for human reviewers.

For each pitch, one single-agent and one multi-agent report are selected from
saved runs and assigned neutral labels ("A"/"B") in a seeded random order. The
mapping label -> system_type is written to a SEPARATE key file that must not be
shared with reviewers.

Example:
    python -m evaluation.blinding --experiment main --run-number 1
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Sequence

import config
from evaluation.rubric import (
    DOMAIN_SUB_ISSUES,
    RATING_COLUMNS,
    SUB_ISSUE_COLUMNS,
    rubric_markdown,
)
from utils.storage import load_all_runs
from utils.validation import find_role_mentions

KEY_COLUMNS = ("pitch_id", "report_label", "system_type", "run_id", "run_number", "json_path")


def select_reports(experiment: str, run_number: int, subdir: str | None) -> dict[str, dict[str, dict]]:
    """Return ``{pitch_id: {system_type: record}}`` for the chosen experiment/run."""
    chosen: dict[str, dict[str, dict]] = {}
    for record in load_all_runs(subdir):
        if record.get("experiment") != experiment or record.get("run_number") != run_number:
            continue
        chosen.setdefault(record["pitch_id"], {})[record["system_type"]] = record
    return {pid: recs for pid, recs in chosen.items() if set(recs) == set(config.SYSTEM_TYPES)}


def export_blinded(
    experiment: str = "main",
    run_number: int = 1,
    subdir: str | None = None,
    out_dir: Path | None = None,
    seed: int = config.RANDOM_SEED,
    reviewer_ids: Sequence[str] = ("R1",),
) -> Path:
    """Write blinded Markdown reports, rating templates, rubric and the secret key file."""
    out = out_dir or (config.RATINGS_DIR / "blinded")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    reports = select_reports(experiment, run_number, subdir)
    if not reports:
        raise FileNotFoundError(
            f"No pitch has both a single and a multi run for experiment='{experiment}', run_number={run_number}."
        )

    key_rows: list[dict] = []
    rating_rows: list[dict] = []
    sub_issue_rows: list[dict] = []
    for pitch_id in sorted(reports):
        systems = list(config.SYSTEM_TYPES)
        rng.shuffle(systems)
        for label, system in zip("AB", systems):
            record = reports[pitch_id][system]
            leaks = find_role_mentions(record["report"])
            if leaks:
                print(f"WARNING: {pitch_id} {system} report mentions {leaks}; this may reveal the system to reviewers.")
            (out / f"{pitch_id}_Report_{label}.md").write_text(
                f"# Pitch {pitch_id} - Report {label}\n\n{record['report']}\n", encoding="utf-8"
            )
            key_rows.append({
                "pitch_id": pitch_id, "report_label": label, "system_type": system,
                "run_id": record["run_id"], "run_number": record["run_number"],
                "json_path": f"{record['pitch_id']}_{system}_r{record['run_number']:02d}_{record['run_id']}.json",
            })
            for reviewer in reviewer_ids:
                rating_rows.append({**{c: "" for c in RATING_COLUMNS}, "reviewer_id": reviewer, "pitch_id": pitch_id, "report_label": label})
                for domain, issues in DOMAIN_SUB_ISSUES.items():
                    for issue in issues:
                        sub_issue_rows.append({**{c: "" for c in SUB_ISSUE_COLUMNS}, "reviewer_id": reviewer, "pitch_id": pitch_id, "report_label": label, "domain": domain, "sub_issue": issue})

    _write_csv(out / "ratings_template.csv", rating_rows, RATING_COLUMNS)
    _write_csv(out / "sub_issue_template.csv", sub_issue_rows, SUB_ISSUE_COLUMNS)
    (out / "rubric.md").write_text(rubric_markdown(), encoding="utf-8")
    # Key file lives OUTSIDE the reviewer folder.
    _write_csv(config.RATINGS_DIR / "blinding_key.csv", key_rows, KEY_COLUMNS)
    return out


def _write_csv(path: Path, rows: list[dict], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", default="main")
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--subdir", default=None, help="Restrict to one data/outputs subfolder")
    parser.add_argument("--reviewers", nargs="+", default=["R1"], help="Reviewer ids to pre-fill in templates")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    args = parser.parse_args(argv)
    out = export_blinded(args.experiment, args.run_number, args.subdir, seed=args.seed, reviewer_ids=args.reviewers)
    print(f"Blinded reports + templates: {out}")
    print(f"SECRET key (do not share with reviewers): {config.RATINGS_DIR / 'blinding_key.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
