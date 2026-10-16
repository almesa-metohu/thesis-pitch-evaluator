"""Multi-agent condition: a moderated expert-panel discussion in five stages.

Stage 0  Moderator opening (framing only, no evaluation).
Stage 1  Round 1: four specialists analyse the pitch independently and
         concurrently; they see the pitch and the opening, not each other.
Stage 2  Moderator cross-domain review: 2-4 targeted follow-up questions,
         each addressed to specific specialists.
Stage 3  Round 2: only the addressed specialists respond; they see all Round 1
         analyses and may build on each other's findings.
Stage 4  Moderator synthesis: the final report under the SAME template, length
         budget and token cap as the single agent.

Every message is stored chronologically in ``record["discussion"]``. Token and
cost totals cover ALL calls so the full computational cost is visible.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import config
from agents import (
    SPECIALIST_IDS,
    AgentResult,
    parse_followup_questions,
    run_moderator_followup,
    run_moderator_opening,
    run_moderator_synthesis,
    run_specialist_analysis,
    run_specialist_response,
    specialist_label,
)
from agents.specialist import format_questions
from utils.validation import validate_pitch_text
from workflows.common import build_run_record


def _run_concurrently(jobs: dict[str, Callable[[], AgentResult]]) -> dict[str, AgentResult]:
    """Run ``{name: thunk}`` concurrently (or sequentially per config), preserving order."""
    if config.PARALLEL_SPECIALISTS and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {name: pool.submit(fn) for name, fn in jobs.items()}
            return {name: fut.result() for name, fut in futures.items()}
    return {name: fn() for name, fn in jobs.items()}


def _message(round_no: int, agent_id: str, msg_type: str, result: AgentResult, **extra: Any) -> dict[str, Any]:
    """One chronological discussion entry with the call's measurements."""
    entry: dict[str, Any] = {
        "round": round_no,
        "agent": agent_id,
        "agent_label": specialist_label(agent_id),
        "type": msg_type,
        "content": result.output,
        "latency_seconds": result.latency_seconds,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "word_count": result.word_count,
        "token_count": result.token_count,
        "finish_reason": result.finish_reason,
    }
    entry.update(extra)
    return entry


def run_multi_workflow(
    pitch_text: str,
    pitch_id: str = "adhoc",
    pitch_title: str = "",
    run_number: int = 1,
    experiment: str = "adhoc",
) -> dict[str, Any]:
    """Evaluate ``pitch_text`` with the moderated multi-agent discussion and return the run record."""
    text = validate_pitch_text(pitch_text)
    discussion: list[dict[str, Any]] = []
    results: list[AgentResult] = []
    start = time.perf_counter()

    # Stage 0: opening
    opening = run_moderator_opening(text)
    results.append(opening)
    discussion.append(_message(0, "moderator", "opening", opening))

    # Stage 1: Round 1 analyses (independent, concurrent)
    round1 = _run_concurrently({
        agent_id: (lambda a=agent_id: run_specialist_analysis(a, text, opening.output))
        for agent_id in SPECIALIST_IDS
    })
    for agent_id in SPECIALIST_IDS:
        results.append(round1[agent_id])
        discussion.append(_message(1, agent_id, "analysis", round1[agent_id]))

    # Stage 2: cross-domain review with follow-up questions
    review = run_moderator_followup(text, round1)
    results.append(review)
    questions = parse_followup_questions(review.output)
    discussion.append(_message(2, "moderator", "follow_up", review, questions=questions))

    # Stage 3: Round 2 responses, one message per addressed specialist
    addressed: dict[str, list[dict]] = {}
    for q in questions:
        for agent_id in q["to"]:
            addressed.setdefault(agent_id, []).append(q)
    ordered = {a: addressed[a] for a in SPECIALIST_IDS if a in addressed}
    round2 = _run_concurrently({
        agent_id: (lambda a=agent_id, qs=qs: run_specialist_response(a, text, round1, qs))
        for agent_id, qs in ordered.items()
    })
    for agent_id, result in round2.items():
        results.append(result)
        discussion.append(_message(
            2, agent_id, "response", result,
            question_ids=[q["id"] for q in ordered[agent_id]],
        ))

    # Stage 4: synthesis
    round2_text = "\n\n".join(
        f"<{agent_id}>\n{specialist_label(agent_id)} (answering question(s) "
        f"{', '.join(str(q['id']) for q in ordered[agent_id])}):\n{result.output}\n</{agent_id}>"
        for agent_id, result in round2.items()
    ) or "(no specialist was addressed)"
    final = run_moderator_synthesis(text, round1, format_questions(questions), round2_text)
    results.append(final)
    discussion.append(_message(3, "moderator", "final_report", final))
    wall_clock = time.perf_counter() - start

    return build_run_record(
        pitch_id=pitch_id,
        pitch_title=pitch_title,
        system_type="multi",
        run_number=run_number,
        experiment=experiment,
        final=final,
        latency_seconds=wall_clock,
        sequential_latency_seconds=sum(r.latency_seconds for r in results),
        input_tokens=sum(r.input_tokens for r in results),
        output_tokens=sum(r.output_tokens for r in results),
        estimated_cost_usd=sum(r.estimated_cost_usd for r in results),
        llm_calls=len(results),
        discussion=discussion,
        followup_questions=questions,
    )
