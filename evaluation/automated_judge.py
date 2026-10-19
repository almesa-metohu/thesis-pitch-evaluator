"""Blinded automated evaluation for the main single-vs-multi experiment.

The evaluator is a separate LLM model and is treated as a measurement
instrument, not as human expert judgement. For each pitch, the two final
reports are anonymised as A/B and their order is randomised with the fixed
experiment seed.

Example:
    python3 -m evaluation.automated_judge --experiment main --subdir main
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path
from typing import Sequence

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import config
from utils.storage import get_pitch, load_all_runs

SYSTEM_PROMPT = """You are an independent evaluator for an MSc research experiment comparing two LLM-generated business-pitch evaluations.

Evaluate ONLY the quality of the reports against the supplied source pitch. Do not guess which system produced either report.

Score each report independently using the same rubric:
- specificity: 1-5, where 1 is generic and 5 consistently anchors claims to concrete pitch facts, figures, assumptions, risks and missing information.
- depth_strategy: 0-3 for depth of reasoning on value proposition/business model, competitive position, growth logic and strategic risks.
- depth_technology: 0-3 for technical feasibility, scalability, implementation complexity, dependencies and technical risks.
- depth_finance: 0-3 for revenue model, pricing, costs, margins, assumptions and sustainability.
- depth_marketing: 0-3 for target customer, positioning, acquisition, competition, go-to-market and retention.
- clarity: 1-5 for structure, readability and precision.

Depth scale: 0 not addressed; 1 mentioned only; 2 pitch-specific evidence or reasoning; 3 pitch-specific evidence plus implications and limitations.

Important controls:
- Judge grounding against the pitch, not external business knowledge.
- Do not reward length by itself.
- Do not reward a report for merely mentioning more categories.
- Penalise unsupported claims, invented facts and generic advice.
- Evaluate A and B independently before comparing them.
- Return valid JSON only, with the exact schema requested.
"""

USER_PROMPT = """<pitch>
{pitch}
</pitch>

<report_a>
{report_a}
</report_a>

<report_b>
{report_b}
</report_b>

Return JSON with exactly this structure:
{{
  "A": {{
    "specificity": 1,
    "depth_strategy": 0,
    "depth_technology": 0,
    "depth_finance": 0,
    "depth_marketing": 0,
    "clarity": 1,
    "brief_reason": "one or two sentences"
  }},
  "B": {{
    "specificity": 1,
    "depth_strategy": 0,
    "depth_technology": 0,
    "depth_finance": 0,
    "depth_marketing": 0,
    "clarity": 1,
    "brief_reason": "one or two sentences"
  }}
}}
Use integers only for scores.
"""

SCORE_FIELDS = (
    "specificity",
    "depth_strategy",
    "depth_technology",
    "depth_finance",
    "depth_marketing",
    "clarity",
)


def _select_pairs(experiment: str, subdir: str | None) -> dict[str, dict[str, dict]]:
    pairs: dict[str, dict[str, dict]] = {}
    for r in load_all_runs(subdir):
        if r.get("experiment") != experiment or r.get("run_number") != 1:
            continue
        if r.get("system_type") not in config.SYSTEM_TYPES:
            continue
        pairs.setdefault(r["pitch_id"], {})[r["system_type"]] = r
    return {pid: x for pid, x in pairs.items() if set(x) == set(config.SYSTEM_TYPES)}


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^\`\`\`(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\`\`\`$", "", cleaned)
    return json.loads(cleaned)


def _validate(scores: dict) -> None:
    for label in ("A", "B"):
        if label not in scores:
            raise ValueError(f"Judge response missing {label}")
        row = scores[label]
        for field in SCORE_FIELDS:
            if field not in row or not isinstance(row[field], int):
                raise ValueError(f"{label}.{field} missing or non-integer")
        if not 1 <= row["specificity"] <= 5 or not 1 <= row["clarity"] <= 5:
            raise ValueError(f"{label}: 1-5 score outside range")
        for field in ("depth_strategy", "depth_technology", "depth_finance", "depth_marketing"):
            if not 0 <= row[field] <= 3:
                raise ValueError(f"{label}.{field} outside 0-3")


def run_judge(experiment: str, subdir: str | None, out_dir: Path) -> list[dict]:
    pairs = _select_pairs(experiment, subdir)
    if not pairs:
        raise FileNotFoundError("No complete single/multi report pairs found.")

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(config.RANDOM_SEED)
    model = ChatOpenAI(
        model=config.JUDGE_MODEL,
        temperature=config.JUDGE_TEMPERATURE,
        max_tokens=config.JUDGE_MAX_OUTPUT_TOKENS,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        max_retries=config.MAX_RETRIES,
        api_key=config.get_openai_api_key(),
    )
    prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", USER_PROMPT)])

    rows: list[dict] = []
    for pitch_id in sorted(pairs):
        systems = list(config.SYSTEM_TYPES)
        rng.shuffle(systems)
        mapping = {"A": systems[0], "B": systems[1]}
        pitch = get_pitch(pitch_id)
        messages = prompt.format_messages(
            pitch=pitch.pitch_text,
            report_a=pairs[pitch_id][mapping["A"]]["report"],
            report_b=pairs[pitch_id][mapping["B"]]["report"],
        )
        print(f"judge {pitch_id}: A={mapping['A']} B={mapping['B']} ...", flush=True)
        response = model.invoke(messages)
        scores = _parse_json(response.content if isinstance(response.content, str) else str(response.content))
        _validate(scores)

        for label in ("A", "B"):
            system = mapping[label]
            r = {
                "pitch_id": pitch_id,
                "report_label": label,
                "system_type": system,
                "judge_model": config.JUDGE_MODEL,
                **{k: scores[label][k] for k in SCORE_FIELDS},
                "depth_mean": round(sum(scores[label][k] for k in SCORE_FIELDS if k.startswith("depth_")) / 4, 3),
                "brief_reason": scores[label].get("brief_reason", ""),
                "run_id": pairs[pitch_id][system]["run_id"],
            }
            rows.append(r)

    json_path = out_dir / "automated_judge_results.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = out_dir / "automated_judge_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment", default="main")
    p.add_argument("--subdir", default="main")
    p.add_argument("--out-dir", default=str(config.OUTPUTS_DIR / "automated_evaluation"))
    args = p.parse_args(argv)
    rows = run_judge(args.experiment, args.subdir, Path(args.out_dir))
    print(f"Saved {len(rows)} scored reports to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
