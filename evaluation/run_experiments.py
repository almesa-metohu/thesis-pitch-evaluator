"""Batch experiment runner for the main single-vs-multi comparison.

Example:
    python -m evaluation.run_experiments --systems single multi --runs 1
    python -m evaluation.run_experiments --pitch-ids P01 P02 --runs 3
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import config
from utils.storage import Pitch, load_pitches, save_run
from workflows import WORKFLOWS


def run_batch(
    pitches: Sequence[Pitch],
    systems: Sequence[str],
    runs: int,
    experiment: str,
    subdir: str,
    include_variants: bool = False,
) -> list[dict]:
    """Run every (pitch, system, run_number) combination and save each record."""
    records: list[dict] = []
    selected = [p for p in pitches if include_variants or p.variant_of is None]
    total = len(selected) * len(systems) * runs
    done = 0
    for pitch in selected:
        for run_number in range(1, runs + 1):
            for system in systems:
                done += 1
                print(f"[{done}/{total}] {pitch.pitch_id} {system} run {run_number} ...", end=" ", flush=True)
                try:
                    record = WORKFLOWS[system](
                        pitch.pitch_text, pitch.pitch_id, pitch.title, run_number, experiment
                    )
                except Exception as exc:  # noqa: BLE001 - keep the batch going
                    print(f"FAILED: {exc}")
                    continue
                path = save_run(record, subdir)
                records.append(record)
                print(
                    f"{record['word_count']} words, {record['latency_seconds']:.1f}s, "
                    f"${record['estimated_cost_usd']:.4f} -> {path.name}"
                )
    return records


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--systems", nargs="+", choices=config.SYSTEM_TYPES, default=list(config.SYSTEM_TYPES))
    parser.add_argument("--pitch-ids", nargs="*", help="Subset of pitch ids (default: all base pitches)")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per pitch and system")
    parser.add_argument("--experiment", default="main", help="Experiment label stored with each run")
    parser.add_argument("--subdir", default=None, help="Output subfolder under data/outputs (default: experiment name)")
    parser.add_argument("--include-variants", action="store_true", help="Also run sensitivity variant pitches")
    args = parser.parse_args(argv)

    pitches = load_pitches()
    if args.pitch_ids:
        pitches = [p for p in pitches if p.pitch_id in set(args.pitch_ids)]
        missing = set(args.pitch_ids) - {p.pitch_id for p in pitches}
        if missing:
            print(f"Unknown pitch ids: {sorted(missing)}", file=sys.stderr)
            return 1
    if not pitches:
        print("No pitches found in data/pitches.", file=sys.stderr)
        return 1

    print(f"Settings: {config.generation_settings()}")
    records = run_batch(pitches, args.systems, args.runs, args.experiment, args.subdir or args.experiment, args.include_variants)
    print(f"Saved {len(records)} runs. Flat log: {config.RUNS_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
