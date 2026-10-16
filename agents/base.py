"""Shared helper for running one agent as a single controlled LLM call."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from agents.llm_client import LLMResult, call_llm


@dataclass
class AgentResult:
    """Output of one agent plus its measurements."""

    agent: str
    output: str
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    word_count: int
    token_count: int
    finish_reason: str | None

    def to_dict(self) -> dict:
        """Plain dict for JSON storage."""
        return asdict(self)


def run_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    variables: dict[str, str],
) -> AgentResult:
    """Run one agent with the shared generation settings and wrap the result."""
    result: LLMResult = call_llm(
        system_prompt, user_prompt, max_tokens, template_variables=variables
    )
    return AgentResult(
        agent=agent_name,
        output=result.text,
        latency_seconds=result.latency_seconds,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        estimated_cost_usd=result.estimated_cost_usd,
        word_count=result.word_count,
        token_count=result.local_token_count,
        finish_reason=result.finish_reason,
    )
