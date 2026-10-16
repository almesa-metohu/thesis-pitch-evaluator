"""Moderator: opening, cross-domain follow-up questions, and final synthesis."""

from __future__ import annotations

import re

import config
from agents.base import AgentResult, run_agent
from prompts import (
    MODERATOR_FOLLOWUP_SYSTEM_PROMPT,
    MODERATOR_FOLLOWUP_USER_PROMPT,
    MODERATOR_OPENING_SYSTEM_PROMPT,
    MODERATOR_OPENING_USER_PROMPT,
    MODERATOR_SYSTEM_PROMPT,
    MODERATOR_USER_PROMPT,
)

# Words in a "To:" line that map to a specialist id.
_ADDRESSEE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("ceo", "ceo"),
    ("cto", "cto"),
    ("cfo", "cfo"),
    ("marketing", "marketing"),
    ("sales", "marketing"),
)
_QUESTION_BLOCK_RE = re.compile(r"^#{2,4}\s*Question\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
_TO_RE = re.compile(r"^\s*\**To\**\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_QUESTION_RE = re.compile(r"^\s*\**Question\**\s*:\s*(.+)", re.IGNORECASE | re.MULTILINE | re.DOTALL)


def run_moderator_opening(pitch_text: str) -> AgentResult:
    """Stage 0: frame the task and name the issues; no evaluation."""
    return run_agent(
        "moderator",
        MODERATOR_OPENING_SYSTEM_PROMPT,
        MODERATOR_OPENING_USER_PROMPT,
        config.MODERATOR_OPENING_MAX_OUTPUT_TOKENS,
        {"pitch_text": pitch_text},
    )


def run_moderator_followup(pitch_text: str, round1: dict[str, AgentResult]) -> AgentResult:
    """Stage 2: cross-domain review producing targeted follow-up questions."""
    return run_agent(
        "moderator",
        MODERATOR_FOLLOWUP_SYSTEM_PROMPT,
        MODERATOR_FOLLOWUP_USER_PROMPT,
        config.MODERATOR_FOLLOWUP_MAX_OUTPUT_TOKENS,
        {
            "pitch_text": pitch_text,
            "ceo_output": round1["ceo"].output,
            "cto_output": round1["cto"].output,
            "cfo_output": round1["cfo"].output,
            "marketing_output": round1["marketing"].output,
        },
    )


def parse_addressees(to_line: str) -> list[str]:
    """Map a 'To:' line to specialist ids, in panel order, without duplicates."""
    lowered = to_line.lower()
    found = {agent_id for keyword, agent_id in _ADDRESSEE_KEYWORDS if keyword in lowered}
    return [a for a in ("ceo", "cto", "cfo", "marketing") if a in found]


def parse_followup_questions(text: str, max_questions: int = config.MAX_FOLLOWUP_QUESTIONS) -> list[dict]:
    """Extract ``[{"id", "to", "question"}, ...]`` from the Moderator's review text.

    Blocks start with a heading like ``### Question 1`` and contain a ``To:`` line
    and a ``Question:`` line. Blocks without a recognisable addressee are
    skipped. If nothing can be parsed, the whole review is sent to all four
    specialists as a single question so the discussion never silently stops.
    """
    questions: list[dict] = []
    matches = list(_QUESTION_BLOCK_RE.finditer(text))
    for i, match in enumerate(matches):
        block = text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        to_match = _TO_RE.search(block)
        q_match = _QUESTION_RE.search(block)
        if not to_match or not q_match:
            continue
        addressees = parse_addressees(to_match.group(1))
        body = q_match.group(1).strip()
        if not addressees or not body:
            continue
        questions.append({"id": len(questions) + 1, "to": addressees, "question": body})
        if len(questions) >= max_questions:
            break
    if not questions:
        questions.append({
            "id": 1,
            "to": ["ceo", "cto", "cfo", "marketing"],
            "question": text.strip(),
            "parse_fallback": True,
        })
    return questions


def run_moderator_synthesis(
    pitch_text: str,
    round1: dict[str, AgentResult],
    followup_questions_text: str,
    round2_responses_text: str,
) -> AgentResult:
    """Stage 4: final report under the SAME template and budget as the single agent."""
    return run_agent(
        "moderator",
        MODERATOR_SYSTEM_PROMPT,
        MODERATOR_USER_PROMPT,
        config.MAX_OUTPUT_TOKENS,
        {
            "pitch_text": pitch_text,
            "ceo_output": round1["ceo"].output,
            "cto_output": round1["cto"].output,
            "cfo_output": round1["cfo"].output,
            "marketing_output": round1["marketing"].output,
            "followup_questions": followup_questions_text,
            "round2_responses": round2_responses_text,
        },
    )
