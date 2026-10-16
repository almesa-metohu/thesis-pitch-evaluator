"""Token counting, word counting and cost estimation helpers."""

from __future__ import annotations

import re
from functools import lru_cache

import config


@lru_cache(maxsize=4)
def _encoding(model_name: str):
    """Return a tiktoken encoding for the model, falling back to o200k_base."""
    import tiktoken

    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str, model_name: str = config.MODEL_NAME) -> int:
    """Count tokens in ``text`` using the tokenizer for ``model_name``.

    This is a local estimate; the authoritative usage numbers come from the API
    response and are stored separately as ``input_tokens`` / ``output_tokens``.
    """
    if not text:
        return 0
    return len(_encoding(model_name).encode(text))


_WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def count_words(text: str) -> int:
    """Count words with a simple, transparent regex (hyphenated words count once)."""
    return len(_WORD_RE.findall(text or ""))


def estimate_cost_usd(
    input_tokens: int, output_tokens: int, model_name: str = config.MODEL_NAME
) -> float:
    """Estimate API cost in USD from token usage and the pricing table in config.

    Unknown models return 0.0 and the caller should treat cost as unavailable.
    """
    prices = config.PRICING_USD_PER_1M.get(model_name)
    if prices is None:
        # Try prefix match, e.g. "gpt-4o-mini-2024-07-18" -> "gpt-4o-mini".
        for name, p in sorted(config.PRICING_USD_PER_1M.items(), key=lambda kv: -len(kv[0])):
            if model_name.startswith(name):
                prices = p
                break
    if prices is None:
        return 0.0
    return round(
        input_tokens * prices["input"] / 1_000_000
        + output_tokens * prices["output"] / 1_000_000,
        6,
    )
