"""Thin LLM call wrapper shared by every agent.

LangChain is used only for the chat-model wrapper and prompt templates. All
generation parameters come from ``config`` so that every agent in every
condition uses identical settings. The function returns the text plus the
measurements the thesis needs (tokens, latency, cost).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate

import config
from utils.token_utils import count_tokens, count_words, estimate_cost_usd


@dataclass
class LLMResult:
    """Result of one LLM call with the measurements recorded for the thesis."""

    text: str
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    word_count: int
    local_token_count: int
    model: str
    finish_reason: str | None = None
    extra: dict = field(default_factory=dict)


@lru_cache(maxsize=8)
def _chat_model(max_tokens: int):
    """Build (and cache) a ChatOpenAI client with the shared generation settings."""
    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": config.MODEL_NAME,
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "max_tokens": max_tokens,
        "timeout": config.REQUEST_TIMEOUT_SECONDS,
        "max_retries": config.MAX_RETRIES,
        "api_key": config.get_openai_api_key(),
    }
    if config.LLM_SEED is not None:
        kwargs["seed"] = config.LLM_SEED
    return ChatOpenAI(**kwargs)


def _mock_response(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    """Deterministic fake output used when PITCH_EVAL_MOCK=1 (no API calls)."""
    import hashlib

    digest = hashlib.sha1((system_prompt + user_prompt).encode()).hexdigest()[:8]
    if "OPENING STATEMENT" in system_prompt:
        return (
            f"[MOCK {digest}] The panel will evaluate the pitch. Issues to examine: growth plan versus "
            "funding (CEO Agent, CFO Agent); cost per unit versus price (CFO Agent, CTO Agent); "
            "acquisition channel versus target customer (Sales/Marketing Agent)."
        )
    if "CROSS-DOMAIN REVIEW" in system_prompt:
        return (
            f"## Cross-Domain Issues\n- [MOCK {digest}] Growth plan depends on uncosted acquisition.\n"
            "- Third-party dependency affects margins.\n\n## Follow-up Questions\n"
            "### Question 1\nTo: CEO Agent, CFO Agent\nQuestion: How does the missing acquisition cost "
            "affect the viability of the stated expansion plan?\n"
            "### Question 2\nTo: CTO Agent, CFO Agent\nQuestion: What effect does the third-party "
            "dependency have on scalability and margins?\n"
        )
    if "Response to Question N" in user_prompt:
        return (
            f"### Response to Question 1\n[MOCK {digest}] Building on the CFO Agent's figures, the "
            "expansion plan cannot be costed.\nBottom line: viability unproven.\n"
        )
    if "FINAL REPORT" in system_prompt.upper() or "Overall Assessment" in system_prompt:
        words_per_section = max(20, (config.TARGET_OUTPUT_WORDS // len(config.REPORT_SECTIONS)) - 8)
        body = " ".join(["evidence"] * words_per_section)
        parts = [
            f"## {i}. {name}\n\n[MOCK {digest}] {body}\n"
            for i, name in enumerate(config.REPORT_SECTIONS, start=1)
        ]
        return "\n".join(parts)
    return (
        f"[MOCK {digest}] Specialist analysis.\n\n- Finding one based on pitch evidence.\n"
        "- Finding two (assumption, not stated in pitch).\n- Risk: unvalidated demand.\n"
        "- Missing information: pricing details.\n"
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    *,
    template_variables: dict[str, str] | None = None,
) -> LLMResult:
    """Call the LLM once with the shared settings and return text + measurements.

    Args:
        system_prompt: Role/task instructions (may contain ``{placeholders}``).
        user_prompt: The user turn (may contain ``{placeholders}``).
        max_tokens: Hard output cap for this call (final vs specialist budgets).
        template_variables: Values for placeholders in either prompt.

    Raises:
        RuntimeError: if the API call fails after the configured retries.
    """
    variables = template_variables or {}
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", user_prompt)]
    )
    messages = prompt.format_messages(**variables)
    rendered_input = "\n".join(m.content for m in messages)

    start = time.perf_counter()
    if config.MOCK_LLM:
        text = _mock_response(messages[0].content, messages[1].content, max_tokens)
        input_tokens = count_tokens(rendered_input)
        output_tokens = count_tokens(text)
        finish_reason = "stop"
    else:
        try:
            response = _chat_model(max_tokens).invoke(messages)
        except Exception as exc:  # noqa: BLE001 - surface a clear error to callers
            raise RuntimeError(f"LLM call failed: {exc}") from exc
        text = response.content if isinstance(response.content, str) else str(response.content)
        usage = response.usage_metadata or {}
        input_tokens = int(usage.get("input_tokens") or count_tokens(rendered_input))
        output_tokens = int(usage.get("output_tokens") or count_tokens(text))
        finish_reason = (response.response_metadata or {}).get("finish_reason")
    latency = time.perf_counter() - start

    return LLMResult(
        text=text.strip(),
        latency_seconds=round(latency, 3),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost_usd=estimate_cost_usd(input_tokens, output_tokens),
        word_count=count_words(text),
        local_token_count=count_tokens(text),
        model=config.MODEL_NAME,
        finish_reason=finish_reason,
    )
