"""Single-agent condition: one call, one report."""

from __future__ import annotations

from typing import Any

from agents import run_single_agent
from utils.validation import validate_pitch_text
from workflows.common import build_run_record


def run_single_workflow(
    pitch_text: str,
    pitch_id: str = "adhoc",
    pitch_title: str = "",
    run_number: int = 1,
    experiment: str = "adhoc",
) -> dict[str, Any]:
    """Evaluate ``pitch_text`` with the single-agent baseline and return the run record."""
    text = validate_pitch_text(pitch_text)
    result = run_single_agent(text)
    return build_run_record(
        pitch_id=pitch_id,
        pitch_title=pitch_title,
        system_type="single",
        run_number=run_number,
        experiment=experiment,
        final=result,
        latency_seconds=result.latency_seconds,
        sequential_latency_seconds=result.latency_seconds,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        llm_calls=1,
    )
