"""Prompt fragments shared by every agent so that both conditions are controlled.

The single-agent prompt and the moderator prompt use the SAME evaluation
principles, the SAME report template and the SAME length instruction. The
specialist prompts use the same principles with a shorter length budget.
"""

from __future__ import annotations

import config

# Rules applied identically to every agent. No personalities, no praise.
EVALUATION_PRINCIPLES = """\
Evaluation principles (apply strictly):
- Use ONLY the pitch as the factual evidence base. Do not import general industry knowledge, benchmarks, typical practices, market facts or technical assumptions.
- Do not invent facts, figures, competitors, costs, customer behaviour, decision-makers, risks or market data that the pitch does not provide.
- Never call something standard, well-established, competitive, reasonable, cheap, expensive, high, low, strong, weak, compelling, proven, scalable or feasible unless the pitch itself contains evidence supporting that exact judgement. Otherwise describe the observable fact and state what evidence is missing.
- Clearly distinguish four categories: (a) facts or claims explicitly stated in the pitch, (b) arithmetic derived only from stated numbers, (c) cautious inference from stated facts, and (d) missing information.
- Prefix important arithmetic with "Derived:" and material inference with "Inference:".
- Do not infer who the buyer, decision-maker or end user is unless the pitch states it. If that distinction is unclear, report it as missing information.
- Be specific: use the actual numbers, customers, channels, technologies, dates and targets in the pitch rather than generic statements.
- When the pitch supplies enough numbers, perform useful simple arithmetic. Examples include price × current units, price × target units, annualised recurring revenue, one-off fees × units, revenue per paying customer, savings-to-price ratio, or stated variable cost as a share of price.
- Never invent a missing value to complete a calculation. State exactly which variable prevents margin, CAC, LTV, runway, payback or break-even from being calculated.
- Avoid generic praise, filler and generic startup advice.
- Recommendations must stay inside the evidence boundary of the pitch. They may request validation, measurement, clarification, testing, costing or evidence collection for a specific identified gap, but must NOT invent new product features, loyalty programmes, consultants, backup teams, new channels, new technologies, financing schemes or other tactics that the pitch did not mention.
- If a useful action would require choosing a tactic that is not in the pitch, recommend the decision or evidence needed, not the tactic itself.
- Use plain professional language and British English.\
"""


def report_template() -> str:
    """Numbered Markdown headings for the shared final report structure."""
    return "\n".join(
        f"## {i}. {name}" for i, name in enumerate(config.REPORT_SECTIONS, start=1)
    )


FINAL_REPORT_STRUCTURE = f"""\
Output format (mandatory): a Markdown report with EXACTLY these eight numbered second-level headings, in this order, and no other top-level sections:

{report_template()}

Formatting and section rules are IDENTICAL for both experimental conditions:
1. Overall Assessment: one compact paragraph of about 80-110 words with a balanced judgement and the two or three factors that most affect viability.
2. Strategic Analysis: exactly 3-4 concise bullets covering business model/value proposition, competitive position, growth logic and strategic dependencies.
3. Technical Analysis: exactly 3-4 concise bullets covering what the pitch specifies, unvalidated technical assumptions, scalability/dependencies and implementation risks.
4. Financial Analysis: exactly 3-5 concise bullets. Include the most decision-relevant arithmetic permitted by the pitch, each explicitly labelled "Derived:". Then state which missing variables prevent stronger financial conclusions.
5. Market and Sales Analysis: exactly 3-4 concise bullets covering the stated target segment, acquisition/go-to-market, competition/differentiation and retention evidence.
6. Main Risks: exactly 4 numbered risks, ordered by severity. Each must state the evidence or missing evidence that creates it and the likely consequence.
7. Missing Information: exactly 4-6 bullets containing only information genuinely absent from the pitch and explaining what judgement each item prevents.
8. Prioritised Recommendations: exactly 5 numbered actions, most important first. Each action must be tied to a specific finding, risk or missing item above.

Style controls:
- Do not repeat the same finding in several sections unless a cross-domain consequence must be made explicit.
- Prefer concrete evidence and derived figures over adjectives.
- Keep paragraphs and bullets compact; depth must come from reasoning, not length or formatting.
- Do not mention these formatting instructions in the report.\
"""


def length_instruction(target_words: int, tolerance: int) -> str:
    """Explicit length budget instruction (identical wording for both systems)."""
    low, high = target_words - tolerance, target_words + tolerance
    return (
        f"Length budget (mandatory): the complete output must stay between {low} and {high} words. "
        f"Aim for {target_words - 25}-{target_words + 25} words so normal variation remains safely inside the hard range. "
        f"Use the fixed section format above, remove repetition first, and do not exceed {high} words."
    )


FINAL_LENGTH_INSTRUCTION = length_instruction(config.TARGET_OUTPUT_WORDS, config.OUTPUT_TOLERANCE)

SPECIALIST_LENGTH_INSTRUCTION = (
    f"Length budget (mandatory): approximately {config.SPECIALIST_TARGET_WORDS} words in total, "
    f"and no more than {config.SPECIALIST_TARGET_WORDS + 100} words."
)

def length_reminder(target_words: int, tolerance: int) -> str:
    """Short numeric reminder placed at the END of the user turn (identical for both systems)."""
    return (
        f"Reminder: the complete output must be between {target_words - tolerance} and "
        f"{target_words + tolerance} words (target about {target_words})."
    )


FINAL_LENGTH_REMINDER = length_reminder(config.TARGET_OUTPUT_WORDS, config.OUTPUT_TOLERANCE)
SPECIALIST_LENGTH_REMINDER = (
    f"Reminder: the complete output must be about {config.SPECIALIST_TARGET_WORDS} words and "
    f"no more than {config.SPECIALIST_TARGET_WORDS + 100} words."
)


def specialist_output_format(domain_label: str) -> str:
    """Analytical-notes format shared by the four specialists.

    Specialists write notes for the Moderator, not a polished report, so they
    do NOT use the eight-section final template. Every finding must carry its
    evidence and its implication so the Moderator can synthesise rather than
    paraphrase.
    """
    return f"""\
Output format (mandatory): analytical notes for the Moderator, not a polished report for the reader. Use exactly these Markdown headings, in this order:

## {domain_label} Assessment
## Evidence from Pitch
## Key Findings
## Critical Assumptions
## Risks
## Missing Information
## Domain-Specific Recommendations

Section rules:
- {domain_label} Assessment: two to four sentences giving your domain verdict and the decisive factors behind it.
- Evidence from Pitch: bullets listing every fact, figure, claim or quote in the pitch that is relevant to your domain. Copy numbers exactly as stated. Do not interpret here.
- Key Findings: three to six bullets. Each bullet MUST contain three labelled parts on separate lines: "Finding:" (the point), "Evidence:" (the pitch facts it rests on, or "none stated" when the finding rests on an absence), "Implication:" (why it matters and what it changes for the venture).
- Critical Assumptions: the assumptions, stated or implied, that the founders' plan depends on in your domain. For each, say what evidence would confirm or refute it.
- Risks: most severe first. For each, give the mechanism by which it causes harm, not only its label.
- Missing Information: specific items a reviewer would need, and for each what judgement it prevents.
- Domain-Specific Recommendations: concrete actions, each tied to a finding or risk above; most important first.\
"""

_PITCH_BLOCK = """\
Business pitch to evaluate:

<pitch>
{pitch_text}
</pitch>

Produce your evaluation now, following the required output format and length budget exactly.
"""

# Round 1: each specialist receives the pitch and the Moderator's opening.
SPECIALIST_ROUND1_USER_PROMPT = """\
Moderator's opening to the panel:

<moderator_opening>
{moderator_opening}
</moderator_opening>

Business pitch to evaluate:

<pitch>
{pitch_text}
</pitch>

Provide your Round 1 domain analysis now, following the required output format and length budget exactly. Address the issues the Moderator raised that fall in your domain, but do not limit yourself to them.
""" + SPECIALIST_LENGTH_REMINDER

RESPONSE_LENGTH_REMINDER = (
    f"Reminder: your response must be about {config.RESPONSE_TARGET_WORDS} words and "
    f"no more than {config.RESPONSE_TARGET_WORDS + 100} words."
)

# Round 2: only specialists addressed by the Moderator respond.
SPECIALIST_ROUND2_USER_PROMPT = """\
Business pitch (reference):

<pitch>
{pitch_text}
</pitch>

Round 1 analyses from all four specialists (your own is marked with your role):

<round1>
{round1_notes}
</round1>

The Moderator has addressed the following follow-up question(s) to you:

<moderator_questions>
{moderator_questions}
</moderator_questions>

Answer the Moderator now. Rules for this response:
- Answer each question directly, under a heading "### Response to Question N" (use the question numbers given).
- Do not repeat your Round 1 analysis; build on it. Reference specific findings or figures from other specialists' Round 1 notes where they bear on the question, naming the specialist (for example "the CTO Agent's point that ...").
- Where the combination of findings changes a conclusion, say what changes and why. Where it does not, say so and explain what evidence would be needed.
- Keep every statement anchored to the pitch or to a specialist finding; do not introduce new facts.
- Do not invent implementation tactics or remedies that are absent from the pitch. In particular, do not introduce consultants, backup teams, loyalty programmes, discounts, financing schemes, new marketing channels, new product features or new technologies. If action is needed, state what must be validated, measured, clarified, tested or costed.
- Finish each response with one line starting "Bottom line:" stating the net implication for the venture.
""" + RESPONSE_LENGTH_REMINDER

# Sentence appended to every specialist system prompt.
PANEL_NOTE = (
    "You are one member of a moderated expert panel. The Moderator opens the discussion, each specialist "
    "gives a Round 1 analysis, the Moderator then asks targeted cross-domain follow-up questions, and the "
    "specialists addressed answer in Round 2 before the Moderator writes the synthesis. In Round 2 you may "
    "and should use findings made by other specialists; in Round 1 you work only from the pitch."
)

# Used by the single agent; the moderator synthesis user prompt ends with the SAME reminder.
FINAL_PITCH_USER_PROMPT = _PITCH_BLOCK + FINAL_LENGTH_REMINDER


# Shared neutral repair prompt used ONLY when a final report misses the common
# word-count budget. It is deliberately identical for both experimental conditions.
FINAL_LENGTH_REWRITE_SYSTEM_PROMPT = f"""\
You are a neutral report editor. Your ONLY task is to bring an already-written business-pitch evaluation into the required word-count range without changing its analytical content.

Rules:
- Preserve exactly the same eight numbered headings and their order.
- Preserve all evidence, calculations, derived metrics, risks, missing information and recommendations that materially affect the conclusions.
- Do not add new analysis, facts, benchmarks, assumptions or external knowledge.
- Do not strengthen or weaken the conclusions.
- If the draft is too long, target about {config.TARGET_OUTPUT_WORDS} words by removing repetition, filler, duplicated explanations and non-decisive wording first.
- If the draft is too short, target about {config.TARGET_OUTPUT_WORDS} words by clarifying existing reasoning only; do not introduce new findings.
- Conform the report exactly to the shared visible template, including the exact bold labels in sections 2-5, four numbered risks, five missing-information bullets and five numbered recommendations.
- Remove any internal headings such as "Key Findings", "Assessment", "Evidence", "Risks" or "Recommendations".
- Preserve every material "Derived:" calculation already present and do not create a new calculation that was absent from the draft.
- Keep claims grounded only in the pitch and the existing draft.
- The rewritten report must contain NO commentary about editing or word count.

{FINAL_REPORT_STRUCTURE}

{FINAL_LENGTH_INSTRUCTION}
"""

FINAL_LENGTH_REWRITE_USER_PROMPT = """\
Rewrite the report below so it complies with the mandatory final-report word budget while preserving its substantive content.

Current report:
<report>
{report_text}
</report>

Current word count: {current_word_count}

Return only the corrected report.
""" + FINAL_LENGTH_REMINDER
