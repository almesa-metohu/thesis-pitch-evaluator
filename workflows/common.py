"""Shared record-building logic so both workflows log identical fields."""

from __future__ import annotations

from typing import Any

import config
from agents.base import AgentResult, run_agent
from prompts.shared import (
    FINAL_LENGTH_REWRITE_SYSTEM_PROMPT,
    FINAL_LENGTH_REWRITE_USER_PROMPT,
    FINAL_QC_REWRITE_SYSTEM_PROMPT,
    FINAL_QC_REWRITE_USER_PROMPT,
)
from utils.storage import new_run_id, utc_timestamp
from utils.validation import (
    final_report_issues,
    find_missing_sections,
    find_role_mentions,
    within_length_budget,
)


def enforce_final_report_quality(final: AgentResult) -> tuple[AgentResult, list[AgentResult], list[str]]:
    """Apply identical reviewer-facing QC to either experimental condition.

    A deterministic validator checks length, exact visible structure, blinding,
    unsupported judgement terms and invented tactics. If any issue is found,
    the SAME neutral editor repairs the existing report. No pitch text is
    supplied to the editor, so the repair cannot add condition-specific analysis.
    """
    current = final
    corrections: list[AgentResult] = []
    issues = final_report_issues(current.output, current.word_count)

    for _ in range(config.MAX_FINAL_LENGTH_RETRIES):
        if not issues:
            break
        current = run_agent(
            "final_qc_editor",
            FINAL_QC_REWRITE_SYSTEM_PROMPT,
            FINAL_QC_REWRITE_USER_PROMPT,
            config.MAX_OUTPUT_TOKENS,
            {
                "report_text": current.output,
                "issues": "\n".join(f"- {issue}" for issue in issues),
            },
        )
        corrections.append(current)
        issues = final_report_issues(current.output, current.word_count)

    return current, corrections, issues


def build_run_record(
    *,
    pitch_id: str,
    pitch_title: str,
    system_type: str,
    run_number: int,
    experiment: str,
    final: AgentResult,
    latency_seconds: float,
    sequential_latency_seconds: float,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    llm_calls: int,
    discussion: list[dict[str, Any]] | None = None,
    followup_questions: list[dict[str, Any]] | None = None,
    final_length_correction_calls: int = 0,
    final_qc_issues: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the structured metadata saved for every generated report.

    ``final`` is the report that enters the comparison (single-agent report or
    moderator synthesis). Token and cost totals cover ALL calls of the condition
    so that the multi-agent system's full computational cost is visible.
    """
    record: dict[str, Any] = {
        "run_id": new_run_id(),
        "pitch_id": pitch_id,
        "pitch_title": pitch_title,
        "system_type": system_type,
        "run_number": run_number,
        "experiment": experiment,
        "model": config.MODEL_NAME,
        "temperature": config.TEMPERATURE,
        "max_output_tokens": config.MAX_OUTPUT_TOKENS,
        "target_output_words": config.TARGET_OUTPUT_WORDS,
        "settings": config.generation_settings(),
        "timestamp": utc_timestamp(),
        "latency_seconds": round(latency_seconds, 3),
        "sequential_latency_seconds": round(sequential_latency_seconds, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(estimated_cost_usd, 6),
        # Measurements of the FINAL report only (what reviewers see).
        "word_count": final.word_count,
        "token_count": final.token_count,
        "final_output_tokens": final.output_tokens,
        "within_length_budget": within_length_budget(final.word_count),
        "missing_sections": find_missing_sections(final.output),
        # Blinding check: role/panel words in the final report (should be empty for both systems).
        "role_mentions": find_role_mentions(final.output),
        "finish_reason": final.finish_reason,
        "llm_calls": llm_calls,
        "final_length_correction_calls": final_length_correction_calls,
        "final_qc_issues": final_qc_issues or [],
        "final_qc_passed": not bool(final_qc_issues),
        "report": final.output,
    }
    if discussion is not None:
        # Chronological panel discussion (multi-agent only). Never exported to
        # reviewers: evaluation/blinding.py writes record["report"] only.
        record["discussion"] = discussion
        record["followup_questions"] = followup_questions or []
        record["discussion_messages"] = len(discussion)
        record["per_agent_latency_seconds"] = {
            f"{m['round']}_{m['agent']}_{m['type']}": m["latency_seconds"] for m in discussion
        }
    return record
