"""Automated consistency sub-study (separate from the human evaluation).

Two concepts are kept apart:

* **Stability**: the SAME pitch is evaluated CONSISTENCY_RUNS times per system
  with identical settings. Agreement between the repeated reports is measured.
* **Sensitivity**: slightly MODIFIED variants of a pitch (``variant_of`` field in
  the dataset) are each evaluated, and the reports for base vs variant are
  compared. A sensitive system should change its judgement when the pitch
  changes materially; this is reported, not scored as good or bad.

Agreement metrics are deliberately simple and transparent:

* ``lexical_jaccard``: Jaccard similarity of content-word sets of two reports.
* ``sequence_ratio``: difflib SequenceMatcher ratio on normalised text.
* ``section_jaccard_mean``: mean lexical Jaccard computed per report section.
* ``risk_overlap`` / ``recommendation_overlap``: Jaccard over the content words of
  the "Main Risks" and "Prioritised Recommendations" bullets.
* ``embedding_cosine``: optional (config.USE_EMBEDDINGS); OpenAI embeddings.

Example:
    python -m evaluation.consistency stability --pitch-ids P01
    python -m evaluation.consistency sensitivity
"""

from __future__ import annotations

import argparse
import difflib
import itertools
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Iterable, Sequence

import config
from utils.storage import Pitch, append_csv_row, load_pitches, save_run
from utils.validation import split_sections
from workflows import WORKFLOWS

STOPWORDS = set(
    """a an the and or but if of to in on for with by from as at is are was were be been being
    this that these those it its their there here which who whom what when where why how not no
    than then so such can could may might will would should must do does did has have had having
    into over under between within without also more most less least very much many any some each
    other own same both all one two three up down out about across after before during per vs""".split()
)

_TOKEN_RE = re.compile(r"[a-z][a-z'-]+")
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$", re.MULTILINE)


def content_words(text: str) -> set[str]:
    """Lower-cased alphabetic tokens minus stopwords (a transparent lexical signature)."""
    return {w for w in _TOKEN_RE.findall(text.lower()) if w not in STOPWORDS and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity; 1.0 when both sets are empty."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def bullets(text: str) -> list[str]:
    """Return bullet / numbered items in ``text`` (falls back to sentences)."""
    items = [m.strip() for m in _BULLET_RE.findall(text) if m.strip()]
    if items:
        return items
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def embedding_cosine(text_a: str, text_b: str) -> float | None:
    """Cosine similarity of OpenAI embeddings; None when embeddings are disabled.

    Interface kept deliberately small so it can be swapped for a local model.
    """
    if not config.USE_EMBEDDINGS or config.MOCK_LLM:
        return None
    from langchain_openai import OpenAIEmbeddings

    vecs = OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.get_openai_api_key()).embed_documents([text_a, text_b])
    dot = sum(x * y for x, y in zip(vecs[0], vecs[1]))
    norm = (sum(x * x for x in vecs[0]) ** 0.5) * (sum(y * y for y in vecs[1]) ** 0.5)
    return round(dot / norm, 4) if norm else None


def pairwise_agreement(report_a: str, report_b: str) -> dict[str, float | None]:
    """Compute all agreement metrics between two final reports."""
    sections_a, sections_b = split_sections(report_a), split_sections(report_b)
    section_scores = [
        jaccard(content_words(sections_a[s]), content_words(sections_b[s]))
        for s in config.REPORT_SECTIONS
    ]
    norm_a = " ".join(report_a.lower().split())
    norm_b = " ".join(report_b.lower().split())
    return {
        "lexical_jaccard": round(jaccard(content_words(report_a), content_words(report_b)), 4),
        "sequence_ratio": round(difflib.SequenceMatcher(None, norm_a, norm_b).ratio(), 4),
        "section_jaccard_mean": round(statistics.mean(section_scores), 4),
        "risk_overlap": round(
            jaccard(
                content_words(" ".join(bullets(sections_a["Main Risks"]))),
                content_words(" ".join(bullets(sections_b["Main Risks"]))),
            ),
            4,
        ),
        "recommendation_overlap": round(
            jaccard(
                content_words(" ".join(bullets(sections_a["Prioritised Recommendations"]))),
                content_words(" ".join(bullets(sections_b["Prioritised Recommendations"]))),
            ),
            4,
        ),
        "embedding_cosine": embedding_cosine(report_a, report_b),
    }


def aggregate_pairs(reports: Sequence[str]) -> dict[str, dict[str, float]]:
    """Mean and SD of each metric over all unordered pairs of ``reports``."""
    pairs = [pairwise_agreement(a, b) for a, b in itertools.combinations(reports, 2)]
    out: dict[str, dict[str, float]] = {}
    for metric in pairs[0]:
        values = [p[metric] for p in pairs if p[metric] is not None]
        if values:
            out[metric] = {
                "mean": round(statistics.mean(values), 4),
                "sd": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
                "n_pairs": len(values),
            }
    return out


# ---------------------------------------------------------------------------
# Stability
# ---------------------------------------------------------------------------
STABILITY_COLUMNS = ("pitch_id", "system_type", "n_runs", "metric", "mean", "sd", "n_pairs", "word_count_mean", "word_count_sd")


def run_stability(pitches: Iterable[Pitch], systems: Sequence[str], runs: int, out_dir: Path) -> list[dict]:
    """Run each system ``runs`` times per pitch, save all reports, score agreement."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for pitch in pitches:
        for system in systems:
            records = []
            for run_number in range(1, runs + 1):
                print(f"stability {pitch.pitch_id} {system} run {run_number}/{runs} ...", flush=True)
                record = WORKFLOWS[system](pitch.pitch_text, pitch.pitch_id, pitch.title, run_number, "stability")
                save_run(record, "stability")
                records.append(record)
            reports = [r["report"] for r in records]
            words = [r["word_count"] for r in records]
            agg = aggregate_pairs(reports)
            summary = {
                "pitch_id": pitch.pitch_id,
                "system_type": system,
                "n_runs": runs,
                "run_ids": [r["run_id"] for r in records],
                "word_count_mean": round(statistics.mean(words), 1),
                "word_count_sd": round(statistics.pstdev(words), 1),
                "agreement": agg,
            }
            results.append(summary)
            for metric, stats in agg.items():
                append_csv_row(
                    out_dir / "stability_summary.csv",
                    {**{k: summary[k] for k in ("pitch_id", "system_type", "n_runs", "word_count_mean", "word_count_sd")}, "metric": metric, **stats},
                    STABILITY_COLUMNS,
                )
    (out_dir / "stability_results.json").write_text(json.dumps({"settings": config.generation_settings(), "results": results}, indent=2), encoding="utf-8")
    return results


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------
SENSITIVITY_COLUMNS = ("base_pitch_id", "variant_pitch_id", "system_type", "metric", "value")


def run_sensitivity(pitches: Sequence[Pitch], systems: Sequence[str], out_dir: Path) -> list[dict]:
    """Evaluate base pitches and their variants once each; compare base vs variant."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {p.pitch_id: p for p in pitches}
    variants = [p for p in pitches if p.variant_of]
    if not variants:
        print("No pitches with a 'variant_of' field found; nothing to do.")
        return []
    results = []
    for variant in variants:
        base = by_id.get(variant.variant_of or "")
        if base is None:
            print(f"Variant {variant.pitch_id} refers to unknown base {variant.variant_of}; skipped.")
            continue
        for system in systems:
            print(f"sensitivity {base.pitch_id} vs {variant.pitch_id} [{system}] ...", flush=True)
            base_rec = WORKFLOWS[system](base.pitch_text, base.pitch_id, base.title, 1, "sensitivity")
            var_rec = WORKFLOWS[system](variant.pitch_text, variant.pitch_id, variant.title, 1, "sensitivity")
            save_run(base_rec, "sensitivity")
            save_run(var_rec, "sensitivity")
            metrics = pairwise_agreement(base_rec["report"], var_rec["report"])
            row = {"base_pitch_id": base.pitch_id, "variant_pitch_id": variant.pitch_id, "system_type": system, "agreement_base_vs_variant": metrics, "base_run_id": base_rec["run_id"], "variant_run_id": var_rec["run_id"]}
            results.append(row)
            for metric, value in metrics.items():
                if value is not None:
                    append_csv_row(out_dir / "sensitivity_summary.csv", {"base_pitch_id": base.pitch_id, "variant_pitch_id": variant.pitch_id, "system_type": system, "metric": metric, "value": value}, SENSITIVITY_COLUMNS)
    (out_dir / "sensitivity_results.json").write_text(json.dumps({"settings": config.generation_settings(), "results": results}, indent=2), encoding="utf-8")
    return results


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("study", choices=["stability", "sensitivity"])
    parser.add_argument("--systems", nargs="+", choices=config.SYSTEM_TYPES, default=list(config.SYSTEM_TYPES))
    parser.add_argument("--pitch-ids", nargs="*", help="Base pitch ids (default: all)")
    parser.add_argument("--runs", type=int, default=config.CONSISTENCY_RUNS)
    parser.add_argument("--out-dir", default=str(config.OUTPUTS_DIR / "consistency"))
    args = parser.parse_args(argv)

    pitches = load_pitches()
    out_dir = Path(args.out_dir)
    if args.study == "stability":
        selected = [p for p in pitches if p.variant_of is None and (not args.pitch_ids or p.pitch_id in args.pitch_ids)]
        if not selected:
            print("No matching pitches.", file=sys.stderr)
            return 1
        results = run_stability(selected, args.systems, args.runs, out_dir)
        for r in results:
            lj = r["agreement"].get("lexical_jaccard", {})
            print(f"{r['pitch_id']} {r['system_type']}: lexical_jaccard mean={lj.get('mean')} sd={lj.get('sd')} | words {r['word_count_mean']} +/- {r['word_count_sd']}")
    else:
        if args.pitch_ids:
            pitches = [p for p in pitches if p.pitch_id in args.pitch_ids or p.variant_of in args.pitch_ids]
        results = run_sensitivity(pitches, args.systems, out_dir)
        for r in results:
            print(f"{r['base_pitch_id']} vs {r['variant_pitch_id']} [{r['system_type']}]: {r['agreement_base_vs_variant']}")
    print(f"Results written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
