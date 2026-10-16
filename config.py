"""Central experimental configuration for the thesis prototype.

Every setting that could influence the single-agent vs multi-agent comparison
lives here so that both conditions provably share the same values. Change
settings in this file only; do not hard-code them elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"
PITCHES_DIR: Path = DATA_DIR / "pitches"
OUTPUTS_DIR: Path = DATA_DIR / "outputs"
RATINGS_DIR: Path = DATA_DIR / "ratings"
RUNS_CSV: Path = OUTPUTS_DIR / "runs.csv"

load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# LLM generation settings (IDENTICAL for every experimental condition)
# ---------------------------------------------------------------------------
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
TEMPERATURE: float = 0.2
TOP_P: float = 1.0
# Optional OpenAI "seed" parameter. Leave as None for the consistency study so
# natural sampling variability is measured rather than suppressed.
LLM_SEED: int | None = None
REQUEST_TIMEOUT_SECONDS: int = 120
MAX_RETRIES: int = 2

# ---------------------------------------------------------------------------
# Output length control (the supervisor identified length as a confound)
# ---------------------------------------------------------------------------
# Both FINAL reports (single-agent report and moderator report) share this budget.
TARGET_OUTPUT_WORDS: int = 900
OUTPUT_TOLERANCE: int = 100
# Hard token cap for final reports. 1000 words is roughly 1,350 tokens; the cap
# leaves headroom so the model is not cut mid-sentence, while preventing runaway
# length. The SAME cap applies to the single-agent report and the moderator report.
MAX_OUTPUT_TOKENS: int = 1700
# If a final report falls outside the shared word budget, both conditions use
# the same neutral length-correction step. The correction may only compress or
# expand the existing draft; it may not add new analysis.
MAX_FINAL_LENGTH_RETRIES: int = 2

# Intermediate specialist outputs may be shorter. They are inputs to the
# moderator and are NOT compared against the single-agent report.
SPECIALIST_TARGET_WORDS: int = 500
SPECIALIST_MAX_OUTPUT_TOKENS: int = 1200

# Run the four specialists concurrently (affects wall-clock latency only; the
# sequential-equivalent latency is also recorded).
PARALLEL_SPECIALISTS: bool = True

# ---------------------------------------------------------------------------
# Moderated discussion (multi-agent condition only)
# ---------------------------------------------------------------------------
# Stage 0: moderator opening (framing only, no evaluation).
MODERATOR_OPENING_TARGET_WORDS: int = 150
MODERATOR_OPENING_MAX_OUTPUT_TOKENS: int = 400
# Stage 2: moderator cross-domain review with targeted follow-up questions.
MIN_FOLLOWUP_QUESTIONS: int = 2
MAX_FOLLOWUP_QUESTIONS: int = 4
MODERATOR_FOLLOWUP_MAX_OUTPUT_TOKENS: int = 700
# Stage 3: specialist responses to the follow-up questions (shorter than round 1).
RESPONSE_TARGET_WORDS: int = 300
RESPONSE_MAX_OUTPUT_TOKENS: int = 800

# ---------------------------------------------------------------------------
# Experiment design
# ---------------------------------------------------------------------------
CONSISTENCY_RUNS: int = 5
RANDOM_SEED: int = 42  # local randomisation only (e.g. blinding order)
SYSTEM_TYPES: tuple[str, ...] = ("single", "multi")

# Final report structure shared by BOTH systems. Order matters.
REPORT_SECTIONS: tuple[str, ...] = (
    "Overall Assessment",
    "Strategic Analysis",
    "Technical Analysis",
    "Financial Analysis",
    "Market and Sales Analysis",
    "Main Risks",
    "Missing Information",
    "Prioritised Recommendations",
)

# ---------------------------------------------------------------------------
# Cost estimation (USD per 1 million tokens). Update if OpenAI prices change.
# Estimated cost is derived from reported usage, so the comparison between
# systems remains valid even if absolute prices are slightly out of date.
# ---------------------------------------------------------------------------
PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
}

# Optional embedding model for the consistency study (disabled by default).
USE_EMBEDDINGS: bool = False
EMBEDDING_MODEL: str = "text-embedding-3-small"

# Set PITCH_EVAL_MOCK=1 to replace the LLM with a deterministic fake for
# testing commands without API cost.
MOCK_LLM: bool = os.getenv("PITCH_EVAL_MOCK", "0") == "1"


def get_openai_api_key() -> str:
    """Return the OpenAI API key from the environment or raise a clear error."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key and not MOCK_LLM:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or set PITCH_EVAL_MOCK=1 to run with a fake LLM."
        )
    return key


def generation_settings() -> dict[str, object]:
    """Snapshot of all generation settings, saved with every experiment record."""
    return {
        "model": MODEL_NAME,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "llm_seed": LLM_SEED,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "specialist_max_output_tokens": SPECIALIST_MAX_OUTPUT_TOKENS,
        "target_output_words": TARGET_OUTPUT_WORDS,
        "output_tolerance": OUTPUT_TOLERANCE,
        "max_final_length_retries": MAX_FINAL_LENGTH_RETRIES,
        "specialist_target_words": SPECIALIST_TARGET_WORDS,
        "parallel_specialists": PARALLEL_SPECIALISTS,
        "moderator_opening_max_output_tokens": MODERATOR_OPENING_MAX_OUTPUT_TOKENS,
        "moderator_followup_max_output_tokens": MODERATOR_FOLLOWUP_MAX_OUTPUT_TOKENS,
        "max_followup_questions": MAX_FOLLOWUP_QUESTIONS,
        "response_target_words": RESPONSE_TARGET_WORDS,
        "response_max_output_tokens": RESPONSE_MAX_OUTPUT_TOKENS,
    }
