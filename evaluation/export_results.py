"""Export final thesis experiment artifacts into a Git-tracked folder.

The normal data/outputs directory is intentionally git-ignored. This utility
copies only the artifacts needed for thesis analysis into thesis_results/ so
they can be committed and inspected from GitHub.

Example:
    python3 -m evaluation.export_results
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Sequence

import config

DEFAULT_DEST = config.PROJECT_ROOT / "thesis_results"


def _copy_file(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _copy_json_dir(src_dir: Path, dst_dir: Path) -> int:
    if not src_dir.exists():
        return 0
    count = 0
    for src in sorted(src_dir.glob("*.json")):
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / src.name)
        count += 1
    return count


def _export_main_runs(dest: Path) -> int:
    """Copy the raw JSON records for the main experiment."""
    return _copy_json_dir(config.OUTPUTS_DIR / "main", dest / "main_runs")


def _export_flat_main_log(dest: Path) -> bool:
    """Write a compact CSV containing only main-experiment rows."""
    src = config.RUNS_CSV
    if not src.exists():
        return False
    with src.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r.get("experiment") == "main"]
    if not rows:
        return False
    out = dest / "main_runs_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return True


def export_results(dest: Path = DEFAULT_DEST) -> dict[str, object]:
    dest.mkdir(parents=True, exist_ok=True)

    status: dict[str, object] = {}
    status["main_run_json_files"] = _export_main_runs(dest)
    status["main_runs_summary_csv"] = _export_flat_main_log(dest)

    auto_src = config.OUTPUTS_DIR / "automated_evaluation"
    status["automated_judge_csv"] = _copy_file(
        auto_src / "automated_judge_results.csv",
        dest / "automated_evaluation" / "automated_judge_results.csv",
    )
    status["automated_judge_json"] = _copy_file(
        auto_src / "automated_judge_results.json",
        dest / "automated_evaluation" / "automated_judge_results.json",
    )

    consistency_src = config.OUTPUTS_DIR / "consistency"
    status["stability_summary_csv"] = _copy_file(
        consistency_src / "stability_summary.csv",
        dest / "stability" / "stability_summary.csv",
    )
    status["stability_results_json"] = _copy_file(
        consistency_src / "stability_results.json",
        dest / "stability" / "stability_results.json",
    )

    manifest = {
        "generation_settings": config.generation_settings(),
        "judge_model": config.JUDGE_MODEL,
        "artifacts": status,
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=str(DEFAULT_DEST))
    args = parser.parse_args(argv)
    dest = Path(args.dest)
    status = export_results(dest)
    print(f"Exported thesis artifacts to: {dest}")
    for key, value in status.items():
        print(f"- {key}: {value}")
    print("")
    print("Next:")
    print("  git add thesis_results")
    print('  git commit -m "Add thesis experiment results"')
    print("  git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
