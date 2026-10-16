"""Single-agent baseline: one LLM call evaluates the whole pitch."""

import config
from agents.base import AgentResult, run_agent
from prompts import FINAL_PITCH_USER_PROMPT, SINGLE_AGENT_SYSTEM_PROMPT


def run_single_agent(pitch_text: str) -> AgentResult:
    """Produce the complete final report from one general-purpose prompt."""
    return run_agent(
        "single_agent",
        SINGLE_AGENT_SYSTEM_PROMPT,
        FINAL_PITCH_USER_PROMPT,
        config.MAX_OUTPUT_TOKENS,
        {"pitch_text": pitch_text},
    )
