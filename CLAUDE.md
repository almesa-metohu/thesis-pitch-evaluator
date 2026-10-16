# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Research prototype for an MSc thesis comparing a **single-agent LLM baseline** against a **role-based multi-agent system** (CEO/CTO/CFO/Marketing specialists + Moderator) for business pitch evaluation. It is a controlled experiment, not a product: the central design goal is that both conditions differ *only* in architecture. Everything else (model, temperature, report template, length budget, token cap, evaluation principles) must stay identical. Keep that invariant when changing anything.

## Commands

All commands run from the project root with the venv active (`source .venv/bin/activate`). Modules are imported as top-level packages (`config`, `agents`, `prompts`, ...), so scripts must be run with `python -m`, not by path.

```bash
pip install -r requirements.txt

# Mock LLM: deterministic fake responses, no API key, no cost. Use for any dev/test run.
export PITCH_EVAL_MOCK=1

# Tests (pytest is NOT installed in the venv; the module has its own runner)
PITCH_EVAL_MOCK=1 python -m tests.test_smoke
# or, if pytest is installed:  PITCH_EVAL_MOCK=1 python -m pytest -q
# single test: there is no pytest -k without pytest; call the function directly:
PITCH_EVAL_MOCK=1 python -c "import tests.test_smoke as t; t.test_validation()"

# Streamlit UI (saves runs to data/outputs/streamlit/)
streamlit run app.py

# Experiment pipeline, in order:
python -m evaluation.run_experiments --systems single multi --runs 1 --experiment main   # 1. generate reports
python -m evaluation.blinding --experiment main --run-number 1 --reviewers R1 R2 R3     # 2. export blinded A/B reports + rating templates
#    reviewers fill data/ratings/ratings.csv (system_type left empty; resolved from blinding_key.csv)
python -m evaluation.analyse_results --ratings data/ratings/ratings.csv --experiment main  # 3. stats + charts -> data/ratings/analysis/

# Consistency sub-study
python -m evaluation.consistency stability --pitch-ids P01    # same pitch, CONSISTENCY_RUNS repeats
python -m evaluation.consistency sensitivity                   # base pitch vs variant_of pitches

# Exploratory only, not a thesis outcome measure
python -m evaluation.llm_judge
```

Real runs need `OPENAI_API_KEY` in `.env` (copy from `.env.example`). `MODEL_NAME` can also be overridden via env.

## Architecture

**Call chain (both conditions):** `workflows/*` -> `agents/*` -> `agents/base.run_agent` -> `agents/llm_client.call_llm` -> `workflows/common.build_run_record` -> `utils/storage.save_run`.

- `config.py` is the single source of truth for every experimental setting. Never hard-code model, temperature, token caps, word budgets or section names elsewhere; `generation_settings()` is snapshotted into every run record.
- `agents/llm_client.py` is the only place that touches the LLM (LangChain `ChatOpenAI`, or `_mock_response` when `PITCH_EVAL_MOCK=1`). It returns an `LLMResult` with API-reported tokens, latency, cost and a local tiktoken count. `_chat_model` is `lru_cache(maxsize=1)` keyed by `max_tokens`.
- `agents/base.run_agent` wraps one call into an `AgentResult`. Every agent file is a thin function that pairs a system prompt with a user prompt and a token cap. Specialists use `SPECIALIST_MAX_OUTPUT_TOKENS`; the single agent and the moderator both use `MAX_OUTPUT_TOKENS`.
- `prompts/shared.py` holds the fragments that enforce the control: `EVALUATION_PRINCIPLES`, `FINAL_REPORT_STRUCTURE` (built from `config.REPORT_SECTIONS`), `FINAL_LENGTH_INSTRUCTION`, `FINAL_LENGTH_REMINDER`. Specialists do NOT use the eight-section template; they write analytical notes in the seven-heading format from `specialist_output_format()` (each key finding carries Finding / Evidence / Implication). `prompts/moderator_prompt.py` holds the three moderator stages; only the synthesis stage embeds the final template and length fragments. The single-agent and moderator prompts must embed these verbatim and their user prompts must *end* with `FINAL_LENGTH_REMINDER`; `tests/test_smoke.py` asserts this. Prompts are deliberately functional with no personas (the test also asserts no fictional names).
- `workflows/multi_workflow.py` is a fixed five-stage moderated panel: moderator opening (no evaluation) -> Round 1, four specialists independent and concurrent -> moderator cross-domain review emitting 2 to 4 follow-up questions in a machine-read "To:/Question:" format (`agents/moderator.parse_followup_questions`, with a fallback to all four) -> Round 2, only addressed specialists respond, seeing all Round 1 notes -> moderator synthesis under the single agent's template and budget. `agents/specialist.py` is the registry (`SPECIALISTS`) and runs both specialist stages; the per-role agent files are thin wrappers. Every message goes into `record["discussion"]` chronologically with its own tokens and latency; token and cost totals sum every call (9 to 11). Mock-mode dispatch in `llm_client._mock_response` keys on marker phrases in the prompts ("OPENING STATEMENT", "CROSS-DOMAIN REVIEW", "Response to Question N", "FINAL REPORT"), so keep those phrases if you edit prompts.
- The final multi-agent report must read as if one anonymous evaluator wrote it. `utils/validation.find_role_mentions` records `role_mentions` on every run, the app flags it, and `evaluation/blinding.py` warns on export. Reviewer exports contain only `record["report"]`; the discussion never reaches reviewers.
- `workflows/common.enforce_final_length` applies the SAME optional neutral repair to either condition when a final report misses the 800-1000-word budget. The editor sees only the existing draft, cannot add new analysis, and is limited to one correction call. That call is included in total latency/tokens/cost and logged as `final_length_correction_calls`. `build_run_record` guarantees both conditions produce the identical record schema (asserted by the smoke test). Measurements of the *final* report (`word_count`, `within_length_budget`, `missing_sections`) use `utils/validation.py`, whose section regexes tolerate numbering and Markdown markers.
- `utils/storage.py`: pitches load from every `*.json`/`*.csv` in `data/pitches/` (fields `pitch_id, title, pitch_text, variant_of, notes`; duplicate ids raise). `save_run` writes `data/outputs/<subdir>/<pitch>_<system>_rNN_<run_id>.json` and appends a flat row to `data/outputs/runs.csv` (`CSV_COLUMNS`). Adding a scalar field to records means updating `CSV_COLUMNS` too.
- `evaluation/`: `rubric.py` defines the human-rating columns (specificity/clarity/usefulness 1-5 Likert; depth per domain as mean of 0-3 sub-issue scores) and is imported by both `blinding.py` and `analyse_results.py`, so column changes propagate from there. `analyse_results.py` pairs by reviewer x pitch and runs Wilcoxon signed-rank per criterion. `consistency.py` computes pairwise lexical/section/bullet agreement (embeddings behind `config.USE_EMBEDDINGS`, off by default).

## Conventions and gotchas

- Pitches with `variant_of` set are sensitivity variants: skipped by `run_experiments` unless `--include-variants`, and used by `consistency sensitivity`.
- `data/outputs/*`, `data/ratings/blinded/`, `blinding_key.csv` and `analysis/` are gitignored. `blinding_key.csv` is the secret A/B mapping; never expose it to reviewers.
- `config.LLM_SEED` is intentionally `None` so the consistency study measures natural sampling variance.
- Cost estimates come from `config.PRICING_USD_PER_1M`; unknown models return 0.0 (prefix match handles dated model names).
