"""OPTIONAL, EXPLORATORY ONLY: LLM-based rating of blinded reports.

This is NOT an outcome measure for the thesis. Human reviewers are the primary
evaluation source. LLM judges have documented biases (position, verbosity and
self-preference bias among others); results from this script may be used only
as a labelled exploratory comparison with the human ratings.

It writes rows in the same ratings schema with reviewer_id="LLM_JUDGE" so the
same analysis script can be applied, clearly separated from human data.

Example:
    python -m evaluation.llm_judge --out data/ratings/llm_judge_ratings.csv
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence

import config
from agents.llm_client import call_llm
from evaluation.rubric import DEPTH_SCALE, DOMAIN_SUB_ISSUES, LIKERT_SCALE, RATING_COLUMNS
from utils.storage import append_csv_row

JUDGE_SYSTEM_PROMPT = """\
You are rating an anonymised business-pitch evaluation report against a fixed rubric. Rate ONLY what is in the report, relative to the pitch. Do not reward length. Return strict JSON with integer fields:
specificity (1-5), clarity (1-5), usefulness (1-5), depth_strategy, depth_technology, depth_finance, depth_marketing (each the mean of 0-3 sub-issue depth scores, given as a number with one decimal), and comments (string, max 40 words).

Likert scale: {likert}
Depth scale per sub-issue: {depth}
Sub-issues per domain: {sub_issues}\
"""

JUDGE_USER_PROMPT = """\
<pitch>
{pitch_text}
</pitch>

<report>
{report}
</report>

Return the JSON object only.\
"""


def judge_report(pitch_text: str, report: str) -> dict:
    """Ask the LLM for rubric scores; returns a dict in the ratings schema."""
    result = call_llm(
        JUDGE_SYSTEM_PROMPT,
        JUDGE_USER_PROMPT,
        400,
        template_variables={
            "likert": json.dumps(LIKERT_SCALE),
            "depth": json.dumps(DEPTH_SCALE),
            "sub_issues": json.dumps(DOMAIN_SUB_ISSUES),
            "pitch_text": pitch_text,
            "report": report,
        },
    )
    match = re.search(r"\{.*\}", result.text, re.DOTALL)
    if not match:
        raise ValueError(f"Judge returned no JSON: {result.text[:200]}")
    return json.loads(match.group(0))


def main(argv: Sequence[str] | None = None) -> int:
    """Rate every blinded report in data/ratings/blinded."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blinded-dir", default=str(config.RATINGS_DIR / "blinded"))
    parser.add_argument("--out", default=str(config.RATINGS_DIR / "llm_judge_ratings.csv"))
    args = parser.parse_args(argv)

    from utils.storage import get_pitch

    print("WARNING: exploratory LLM-judge ratings only; not a thesis outcome measure.")
    blinded = Path(args.blinded_dir)
    out = Path(args.out)
    if out.exists():
        out.unlink()
    for path in sorted(blinded.glob("*_Report_*.md")):
        pitch_id, label = re.match(r"(.+)_Report_([A-Z])\.md", path.name).groups()
        report = path.read_text(encoding="utf-8").split("\n", 2)[-1]
        scores = judge_report(get_pitch(pitch_id).pitch_text, report)
        row = {c: "" for c in RATING_COLUMNS}
        row.update({"reviewer_id": "LLM_JUDGE", "pitch_id": pitch_id, "report_label": label, **{k: scores.get(k, "") for k in RATING_COLUMNS if k in scores}})
        append_csv_row(out, row, RATING_COLUMNS)
        print(f"{pitch_id} Report {label}: {scores}")
    print(f"Written to {out} (exploratory only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
