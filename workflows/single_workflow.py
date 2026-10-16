"""Single-agent condition: one call, one report."""

from __future__ import annotations

from typing import Any

from agents import run_single_agent
from utils.validation import validate_pitch_text
from workflows.common import build_run_record, enforce_final_length


def run_single_workflow(
    pitch_text: str,
    pitch_id: str = "adhoc",
    pitch_title: str = "",
    run_number: int = 1,
    experiment: str = "adhoc",
) -> dict[str, Any]:
    """Evaluate ``pitch_text`` with the single-agent baseline and return the run record."""
    text = validate_pitch_text(pitch_text)
    initial = run_single_agent(text)
    result, corrections = enforce_final_length(initial)
    all_results = [initial, *corrections]
    return build_run_record(
        pitch_id=pitch_id,
        pitch_title=pitch_title,
        system_type="single",
        run_number=run_number,
        experiment=experiment,
        final=result,
        latency_seconds=sum(r.latency_seconds for r in all_results),
        sequential_latency_seconds=sum(r.latency_seconds for r in all_results),
        input_tokens=sum(r.input_tokens for r in all_results),
        output_tokens=sum(r.output_tokens for r in all_results),
        estimated_cost_usd=sum(r.estimated_cost_usd for r in all_results),
        llm_calls=len(all_results),
        final_length_correction_calls=len(corrections),
    )
