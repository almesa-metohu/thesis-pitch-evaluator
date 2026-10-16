"""Input validation and output-structure checks."""

from __future__ import annotations

import re

import config
from utils.token_utils import count_words

MIN_PITCH_WORDS = 30
MAX_PITCH_CHARS = 20_000


class ValidationError(ValueError):
    """Raised when a pitch or report fails validation."""


def validate_pitch_text(pitch_text: str) -> str:
    """Return a stripped pitch or raise ``ValidationError`` with a clear message."""
    text = (pitch_text or "").strip()
    if not text:
        raise ValidationError("The pitch is empty.")
    if count_words(text) < MIN_PITCH_WORDS:
        raise ValidationError(
            f"The pitch is too short ({count_words(text)} words). "
            f"Provide at least {MIN_PITCH_WORDS} words."
        )
    if len(text) > MAX_PITCH_CHARS:
        raise ValidationError(f"The pitch exceeds {MAX_PITCH_CHARS} characters.")
    return text


def find_missing_sections(report: str) -> list[str]:
    """Return the report sections (from config) whose heading is absent.

    Headings are matched case-insensitively and tolerate numbering and
    Markdown markers, e.g. ``## 3. Technical Analysis`` or ``**Main Risks**``.
    """
    missing: list[str] = []
    for section in config.REPORT_SECTIONS:
        pattern = re.compile(
            r"^\s*(?:#+\s*)?(?:\*\*)?\s*(?:\d+[.)]\s*)?" + re.escape(section) + r"\b",
            re.IGNORECASE | re.MULTILINE,
        )
        if not pattern.search(report):
            missing.append(section)
    return missing


# Words that would reveal the multi-agent origin of a report to a blinded reviewer.
ROLE_MENTION_PATTERNS: tuple[str, ...] = (
    r"\bCEO\b", r"\bCTO\b", r"\bCFO\b", r"\bSales/Marketing\b", r"\bAgent\b",
    r"\bModerator\b", r"\bspecialists?\b", r"\bpanel\b", r"\bRound [12]\b",
)


def find_role_mentions(report: str) -> list[str]:
    """Return the role/panel words present in ``report`` (case-sensitive for acronyms).

    A final report must read as if written by one anonymous evaluator; any hit
    here is a blinding risk and is recorded with the run so it can be checked
    before reports are exported to reviewers.
    """
    hits: list[str] = []
    for pattern in ROLE_MENTION_PATTERNS:
        match = re.search(pattern, report)
        if match:
            hits.append(match.group(0))
    return hits


def within_length_budget(word_count: int) -> bool:
    """True if ``word_count`` falls inside TARGET_OUTPUT_WORDS +/- OUTPUT_TOLERANCE."""
    low = config.TARGET_OUTPUT_WORDS - config.OUTPUT_TOLERANCE
    high = config.TARGET_OUTPUT_WORDS + config.OUTPUT_TOLERANCE
    return low <= word_count <= high


def split_sections(report: str) -> dict[str, str]:
    """Split a report into ``{section_name: body_text}`` using the configured headings.

    Text before the first recognised heading is stored under ``"_preamble"``.
    Missing sections map to an empty string.
    """
    positions: list[tuple[int, int, str]] = []
    for section in config.REPORT_SECTIONS:
        pattern = re.compile(
            r"^\s*(?:#+\s*)?(?:\*\*)?\s*(?:\d+[.)]\s*)?" + re.escape(section) + r"[^\n]*\n?",
            re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(report)
        if match:
            positions.append((match.start(), match.end(), section))
    positions.sort()
    result: dict[str, str] = {s: "" for s in config.REPORT_SECTIONS}
    result["_preamble"] = report[: positions[0][0]].strip() if positions else report.strip()
    for i, (_, body_start, section) in enumerate(positions):
        body_end = positions[i + 1][0] if i + 1 < len(positions) else len(report)
        result[section] = report[body_start:body_end].strip()
    return result
