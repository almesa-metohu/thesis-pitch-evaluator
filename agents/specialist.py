"""Specialist registry and the two specialist stages (Round 1 analysis, Round 2 response)."""

from __future__ import annotations

import config
from agents.base import AgentResult, run_agent
from prompts import (
    CEO_SYSTEM_PROMPT,
    CFO_SYSTEM_PROMPT,
    CTO_SYSTEM_PROMPT,
    MARKETING_SYSTEM_PROMPT,
    SPECIALIST_ROUND1_USER_PROMPT,
    SPECIALIST_ROUND2_USER_PROMPT,
)

# Internal id -> (display label, system prompt). Order is the panel order.
SPECIALISTS: dict[str, tuple[str, str]] = {
    "ceo": ("CEO Agent", CEO_SYSTEM_PROMPT),
    "cto": ("CTO Agent", CTO_SYSTEM_PROMPT),
    "cfo": ("CFO Agent", CFO_SYSTEM_PROMPT),
    "marketing": ("Sales/Marketing Agent", MARKETING_SYSTEM_PROMPT),
}

SPECIALIST_IDS: tuple[str, ...] = tuple(SPECIALISTS)


def specialist_label(agent_id: str) -> str:
    """Human-readable label for a specialist id (or the Moderator)."""
    if agent_id == "moderator":
        return "Moderator"
    return SPECIALISTS[agent_id][0]


def run_specialist_analysis(agent_id: str, pitch_text: str, moderator_opening: str) -> AgentResult:
    """Round 1: domain analysis from the pitch and the Moderator's opening."""
    _, system_prompt = SPECIALISTS[agent_id]
    return run_agent(
        agent_id,
        system_prompt,
        SPECIALIST_ROUND1_USER_PROMPT,
        config.SPECIALIST_MAX_OUTPUT_TOKENS,
        {"pitch_text": pitch_text, "moderator_opening": moderator_opening},
    )


def format_round1_notes(round1: dict[str, AgentResult], own_id: str | None = None) -> str:
    """Render the four Round 1 analyses as one block, marking the reader's own notes."""
    parts = []
    for agent_id in SPECIALIST_IDS:
        if agent_id not in round1:
            continue
        label = specialist_label(agent_id)
        marker = " (your own Round 1 analysis)" if agent_id == own_id else ""
        parts.append(f"<{agent_id}>\n{label}{marker}:\n{round1[agent_id].output}\n</{agent_id}>")
    return "\n\n".join(parts)


def format_questions(questions: list[dict]) -> str:
    """Render follow-up questions for a prompt."""
    return "\n\n".join(
        f"Question {q['id']} (to: {', '.join(specialist_label(a) for a in q['to'])}):\n{q['question']}"
        for q in questions
    )


def run_specialist_response(
    agent_id: str,
    pitch_text: str,
    round1: dict[str, AgentResult],
    questions: list[dict],
) -> AgentResult:
    """Round 2: answer the Moderator's follow-up question(s) addressed to this specialist."""
    _, system_prompt = SPECIALISTS[agent_id]
    return run_agent(
        agent_id,
        system_prompt,
        SPECIALIST_ROUND2_USER_PROMPT,
        config.RESPONSE_MAX_OUTPUT_TOKENS,
        {
            "pitch_text": pitch_text,
            "round1_notes": format_round1_notes(round1, own_id=agent_id),
            "moderator_questions": format_questions(questions),
        },
    )
