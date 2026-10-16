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


# Final reviewer-facing format controls. These are deliberately mechanical and
# identical for the single-agent and multi-agent conditions.
FINAL_SECTION_LABELS: dict[str, tuple[str, ...]] = {
    "Strategic Analysis": (
        "Business Model & Value",
        "Competitive Position",
        "Growth Logic",
        "Strategic Dependencies",
    ),
    "Technical Analysis": (
        "Technical Setup",
        "Scalability",
        "Dependencies & Reliability",
        "Implementation Evidence",
    ),
    "Financial Analysis": (
        "Derived Metrics",
        "Revenue & Pricing",
        "Costs & Margins",
        "Funding & Sustainability",
    ),
    "Market and Sales Analysis": (
        "Target Segment",
        "Acquisition & Go-to-Market",
        "Competition & Positioning",
        "Retention Evidence",
    ),
}

# Terms that tend to create unsupported qualitative claims. The final report
# can still present the underlying evidence; it simply must not hide that
# evidence behind an ungrounded adjective.
UNSUPPORTED_JUDGEMENT_PATTERNS: tuple[str, ...] = (
    r"\bcompelling\b",
    r"\bpromising\b",
    r"\battractive\b",
    r"\breasonable\b",
    r"\bwell-established\b",
    r"\buser-friendly\b",
    r"\bstrong value proposition\b",
)

# Tactics that appeared in exploratory outputs despite not being present in the
# pitch. Reviewer-facing reports should ask for evidence/validation instead of
# inventing these remedies.
INVENTED_TACTIC_PATTERNS: tuple[str, ...] = (
    r"\bloyalty program(?:me)?s?\b",
    r"\bexternal consultants?\b",
    r"\bbackup (?:engineering )?teams?\b",
    r"\btiered pricing\b",
    r"\bvehicle manufacturers?\b",
    r"\bonline platforms?\b",
    r"\bdirect marketing\b",
    r"\bfinancing options?\b",
    r"\bloyalty discounts?\b",
)


def _list_count(section_text: str, numbered: bool = False) -> int:
    """Count top-level Markdown list items in one already-split section."""
    if numbered:
        pattern = r"(?m)^\d+[.)]\s+"
    else:
        pattern = r"(?m)^[-*]\s+"
    return len(re.findall(pattern, section_text))


def final_report_issues(report: str, word_count: int | None = None) -> list[str]:
    """Return only the controls required for a fair reviewer-facing comparison.

    Both conditions must use the same length budget, contain the same eight
    top-level sections, and remain blind to system identity. Content quality is
    intentionally left to human reviewers rather than over-constrained by code.
    """
    issues: list[str] = []
    wc = count_words(report) if word_count is None else word_count
    if not within_length_budget(wc):
        low = config.TARGET_OUTPUT_WORDS - config.OUTPUT_TOLERANCE
        high = config.TARGET_OUTPUT_WORDS + config.OUTPUT_TOLERANCE
        issues.append(f"word count {wc} is outside {low}-{high}")

    missing = find_missing_sections(report)
    if missing:
        issues.append("missing sections: " + ", ".join(missing))

    role_hits = find_role_mentions(report)
    if role_hits:
        issues.append("blinding terms present: " + ", ".join(role_hits))

    return issues
