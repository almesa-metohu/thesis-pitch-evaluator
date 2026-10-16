"""Reviewer rubric: criteria and domain sub-issues for depth ratings.

Domain *coverage* is partly guaranteed by construction in the multi-agent
system (one agent per domain), so reviewers rate *depth* per sub-issue
instead of presence/absence. The structure here drives the blinded rating
sheets and the analysis.
"""

from __future__ import annotations

# Main human-evaluation criteria (Likert 1-5).
CRITERIA: tuple[str, ...] = ("specificity", "depth", "clarity", "usefulness")

LIKERT_SCALE: dict[int, str] = {
    1: "Very poor",
    2: "Poor",
    3: "Adequate",
    4: "Good",
    5: "Very good",
}

# Depth scale for each sub-issue (0 = not addressed ... 3 = analysed in depth).
DEPTH_SCALE: dict[int, str] = {
    0: "Not addressed",
    1: "Mentioned only (generic statement, no evidence from the pitch)",
    2: "Addressed with some pitch-specific evidence or reasoning",
    3: "Analysed in depth: pitch-specific evidence, implications and limitations",
}

# Domain -> ordered sub-issues. Reviewers rate each sub-issue on DEPTH_SCALE;
# the domain depth score is the mean of its sub-issue scores.
DOMAIN_SUB_ISSUES: dict[str, tuple[str, ...]] = {
    "strategy": (
        "value_proposition",
        "business_model",
        "competitive_position",
        "growth_logic",
        "strategic_risks",
    ),
    "technology": (
        "feasibility",
        "scalability",
        "implementation_complexity",
        "dependencies",
        "technical_risks",
    ),
    "finance": (
        "revenue_model",
        "pricing",
        "costs",
        "margins",
        "assumptions",
        "sustainability",
    ),
    "marketing": (
        "target_customer",
        "positioning",
        "acquisition",
        "competition",
        "go_to_market",
        "retention",
    ),
}

DOMAINS: tuple[str, ...] = tuple(DOMAIN_SUB_ISSUES)

# Columns of the main ratings CSV (one row per reviewer x pitch x report).
RATING_COLUMNS: tuple[str, ...] = (
    "reviewer_id",
    "pitch_id",
    "report_label",   # blinded label, e.g. "A"; mapped to system_type via the key file
    "system_type",    # left EMPTY in reviewer-facing files; filled in by the analysis
    "specificity",
    "depth_strategy",
    "depth_technology",
    "depth_finance",
    "depth_marketing",
    "clarity",
    "usefulness",
    "comments",
)

# Columns of the optional detailed sub-issue sheet (one row per sub-issue).
SUB_ISSUE_COLUMNS: tuple[str, ...] = (
    "reviewer_id",
    "pitch_id",
    "report_label",
    "domain",
    "sub_issue",
    "depth_0_3",
    "comments",
)


def depth_columns() -> list[str]:
    """Names of the four domain-depth columns in the ratings CSV."""
    return [f"depth_{d}" for d in DOMAINS]


def rubric_markdown() -> str:
    """Human-readable rubric to hand to reviewers."""
    lines = ["# Reviewer rubric", "", "## Overall criteria (1-5)", ""]
    lines += [f"- **{k}**: {v}" for k, v in LIKERT_SCALE.items()]
    lines += [
        "",
        "- **Specificity**: how far statements refer to the concrete pitch rather than generic business advice.",
        "- **Depth of analysis**: rated per domain as the mean of sub-issue depth scores (below).",
        "- **Clarity**: structure, readability and precision of the report.",
        "- **Perceived usefulness**: how actionable the report would be for the founders or an investment committee.",
        "",
        "## Depth scale per sub-issue (0-3)",
        "",
    ]
    lines += [f"- **{k}**: {v}" for k, v in DEPTH_SCALE.items()]
    lines += ["", "## Domain sub-issues", ""]
    for domain, issues in DOMAIN_SUB_ISSUES.items():
        lines.append(f"### {domain.title()}")
        lines += [f"- {issue.replace('_', ' ')}" for issue in issues]
        lines.append("")
    return "\n".join(lines)
