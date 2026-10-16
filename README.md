# Thesis Pitch Evaluator

Research prototype for the MSc Artificial Intelligence thesis
**"A Multi-Agent LLM-Based Business Pitch Evaluation System"**.

The prototype exists to compare, under controlled conditions:

1. a **single-agent LLM baseline** that evaluates a business pitch with one general prompt, and
2. a **role-based multi-agent system** (CEO, CTO, CFO, Sales/Marketing agents plus a Moderator).

It is deliberately minimal: no accounts, no database, no payments, no open-ended debate or voting (the
multi-agent discussion has a fixed two-round structure). Everything that
matters for the experiment lives in `config.py`, `prompts/` and `evaluation/`.

---

## 1. Research purpose

The main research question is whether role-based decomposition improves the perceived quality of an LLM
pitch evaluation compared with an equally well-prompted single agent, and at what computational cost.
Quality is judged by **human reviewers** on four criteria (specificity, depth of analysis, clarity,
perceived usefulness) using blinded reports and a paired design. Consistency is studied in a separate
automated sub-study. An optional LLM judge exists for exploratory comparison only.

## 2. Single-agent architecture

```
pitch ──> Single Agent (one LLM call, all domains) ──> final report (8 sections)
```

`agents/single_agent.py` + `prompts/single_agent_prompt.py`. The prompt is intentionally strong: it carries
the same evaluation principles, the same report template and the same length budget as the moderator, and
explicitly asks for equal rigour across strategy, technology, finance and market/sales.

## 3. Multi-agent architecture: moderated expert panel

```
Stage 0  pitch ──> Moderator opening (frames the issues; NO evaluation)
Stage 1  pitch + opening ──> CEO | CTO | CFO | Sales/Marketing   (Round 1, independent, concurrent)
Stage 2  all Round 1 notes ──> Moderator cross-domain review ──> 2-4 targeted follow-up questions,
                                                                   each addressed to 1-3 specialists
Stage 3  pitch + all Round 1 notes + questions ──> addressed specialists only (Round 2, concurrent);
                                                   they may build on each other's findings
Stage 4  everything ──> Moderator synthesis ──> final report (same 8 sections, same length budget)
```

Specialists write analytical notes in a seven-heading domain format (`prompts/shared.py::specialist_output_format`),
not the final template. Round 1 is independent: specialists see the pitch and the opening, never each other.
The Moderator's follow-up questions are machine-read (`agents/moderator.py::parse_followup_questions`; a
review that cannot be parsed falls back to one question for all four specialists). The final synthesis
(`prompts/moderator_prompt.py::MODERATOR_SYSTEM_PROMPT`) must integrate, preserve calculations, trace
cross-domain chains and never mention the panel: `role_mentions` is recorded for every final report and the
blinding export warns if it is non-empty.

The whole discussion is stored chronologically in `record["discussion"]` and shown in the Streamlit
"Multi-Agent Discussion" view. It is for inspection only: reviewers receive the final report alone.

Final report structure (both systems, enforced by prompt and checked by `utils/validation.py`):

1. Overall Assessment  2. Strategic Analysis  3. Technical Analysis  4. Financial Analysis
5. Market and Sales Analysis  6. Main Risks  7. Missing Information  8. Prioritised Recommendations

## 4. Experimental controls

| Control | Where | Value |
|---|---|---|
| Same model | `config.MODEL_NAME` | `gpt-4o-mini` (change in one place) |
| Same temperature / top_p | `config.TEMPERATURE`, `config.TOP_P` | 0.2 / 1.0 |
| Same hard output cap for both final reports | `config.MAX_OUTPUT_TOKENS` | 1700 tokens |
| Same length budget in both final prompts | `config.TARGET_OUTPUT_WORDS` +/- `OUTPUT_TOLERANCE` | 900 +/- 100 words |
| Same report template | `prompts/shared.py::FINAL_REPORT_STRUCTURE` | 8 numbered sections |
| Same evaluation principles | `prompts/shared.py::EVALUATION_PRINCIPLES` | evidence, no invention, label assumptions |
| Same input | pitch text from `data/pitches/` | |
| Local randomness seeded | `config.RANDOM_SEED` | blinding order |

Specialist agents use a shorter intermediate budget (`SPECIALIST_TARGET_WORDS`, `SPECIALIST_MAX_OUTPUT_TOKENS`);
their outputs feed the moderator and are stored but never compared with the single-agent report.

For every final report the system records `word_count`, `token_count`, `within_length_budget` and
`missing_sections`, so length compliance can be reported rather than assumed. Token and cost totals for the
multi-agent condition include every call of the discussion (typically 9 to 11).

`tests/test_smoke.py` asserts that both final prompts contain the identical template and length instruction.

## 5. Install

```bash
cd thesis-pitch-evaluator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Configure the API key

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

To exercise every command without API calls or cost, set `PITCH_EVAL_MOCK=1` (deterministic fake LLM).

## 7. Run the Streamlit app

```bash
streamlit run app.py
```

Paste or select a pitch, choose Single-Agent / Multi-Agent / Compare Both, click **Run Evaluation**. Each
report is shown with latency, word count, token count and estimated cost, and saved under
`data/outputs/streamlit/`.

## 8. Run batch experiments (main comparison)

```bash
python -m evaluation.run_experiments --systems single multi --runs 1 --experiment main
python -m evaluation.run_experiments --pitch-ids P01 P02 --runs 3
```

Each (pitch, system, run_number) produces one JSON file in `data/outputs/<experiment>/` and one row in
`data/outputs/runs.csv`. Sensitivity variants (`variant_of` set) are skipped unless `--include-variants`.

## 9. Run the consistency study

```bash
# Stability: same pitch, CONSISTENCY_RUNS (5) repetitions per system
python -m evaluation.consistency stability --pitch-ids P01

# Sensitivity: base pitch vs slightly modified variant(s), one run each
python -m evaluation.consistency sensitivity
```

All repeated reports are saved. Agreement metrics (pairwise, mean and SD): lexical Jaccard, difflib sequence
ratio, per-section Jaccard, overlap of risk bullets and recommendation bullets. Embedding cosine similarity is
available behind `config.USE_EMBEDDINGS` (off by default). Results: `data/outputs/consistency/`.

## 10. Human evaluation: blinding and analysis

```bash
# 1. export anonymised reports + rating templates (labels A/B in seeded random order)
python -m evaluation.blinding --experiment main --run-number 1 --reviewers R1 R2 R3
# -> data/ratings/blinded/{pitch}_Report_{A,B}.md, ratings_template.csv, sub_issue_template.csv, rubric.md
# -> data/ratings/blinding_key.csv  (SECRET: do not give to reviewers)

# 2. reviewers fill ratings_template.csv -> save as data/ratings/ratings.csv (leave system_type empty)

# 3. analyse: descriptive stats, paired Wilcoxon signed-rank per criterion, cost/latency, charts
python -m evaluation.analyse_results --ratings data/ratings/ratings.csv --experiment main
```

Rubric (`evaluation/rubric.py`): specificity, clarity and usefulness on a 1-5 Likert scale; **depth** is rated
per domain as the mean of sub-issue depth scores (0-3) so reviewers rate depth rather than presence.
Domains and sub-issues: strategy (value proposition, business model, competitive position, growth logic,
strategic risks), technology (feasibility, scalability, implementation complexity, dependencies, technical
risks), finance (revenue model, pricing, costs, margins, assumptions, sustainability), marketing (target
customer, positioning, acquisition, competition, go-to-market, retention).

The analysis pairs ratings by reviewer x pitch and runs `scipy.stats.wilcoxon` separately for specificity,
each domain depth, overall depth (mean of the four), clarity and usefulness, reporting statistic, p-value,
median difference, number of pairs and number of non-zero pairs. P-values are indicative with small samples;
the script prints that caveat.

Optional, exploratory only: `python -m evaluation.llm_judge` rates the blinded reports with the LLM and writes
`llm_judge_ratings.csv` with `reviewer_id=LLM_JUDGE`. It is not a thesis outcome measure.

## 11. Output file formats

**Run record** (`data/outputs/<experiment>/<pitch>_<system>_rNN_<run_id>.json`):

```json
{
  "run_id": "3641dc8aa7f1", "pitch_id": "P01", "pitch_title": "...",
  "system_type": "single", "run_number": 1, "experiment": "main",
  "model": "gpt-4o-mini", "temperature": 0.2, "max_output_tokens": 1700, "target_output_words": 900,
  "settings": { "...all generation settings..." },
  "timestamp": "2026-10-16T11:20:00+00:00",
  "latency_seconds": 10.9, "sequential_latency_seconds": 10.9,
  "input_tokens": 1000, "output_tokens": 1243, "total_tokens": 2243, "estimated_cost_usd": 0.00092,
  "word_count": 967, "token_count": 1243, "final_output_tokens": 1243,
  "within_length_budget": true, "missing_sections": [], "finish_reason": "stop", "llm_calls": 1,
  "report": "## 1. Overall Assessment ...",
  "role_mentions": [],
  "discussion": [
    { "round": 0, "agent": "moderator", "agent_label": "Moderator", "type": "opening", "content": "...",
      "latency_seconds": 3.2, "input_tokens": 700, "output_tokens": 300, "word_count": 227, "token_count": 300,
      "finish_reason": "stop" },
    { "round": 1, "agent": "ceo", "type": "analysis", ... },
    { "round": 2, "agent": "moderator", "type": "follow_up", "questions": [ {"id": 1, "to": ["ceo", "cfo"], "question": "..."} ], ... },
    { "round": 2, "agent": "cfo", "type": "response", "question_ids": [1, 3], ... },
    { "round": 3, "agent": "moderator", "type": "final_report", ... }
  ],
  "followup_questions": [ ... ], "discussion_messages": 11,
  "per_agent_latency_seconds": { "0_moderator_opening": 3.2, ... }
}
```

`discussion`, `followup_questions`, `discussion_messages` and `per_agent_latency_seconds` exist only for
multi-agent runs. `latency_seconds` is wall-clock (Round 1 and Round 2 run concurrently);
`sequential_latency_seconds` is the sum of all call latencies. `role_mentions` lists role or panel words found
in the final report (a blinding risk; should be empty for both systems).

**Flat log** `data/outputs/runs.csv`: one row per run with the scalar fields above plus `json_path`.

**Pitch dataset** `data/pitches/*.json` or `*.csv`: `pitch_id`, `title`, `pitch_text`, optional
`variant_of` (for sensitivity variants) and `notes`.

**Ratings** `data/ratings/ratings.csv`: `reviewer_id, pitch_id, report_label, system_type, specificity,
depth_strategy, depth_technology, depth_finance, depth_marketing, clarity, usefulness, comments`.
`system_type` is resolved from `blinding_key.csv` when left empty.

**Analysis** `data/ratings/analysis/`: `descriptive_stats.csv`, `wilcoxon_tests.csv`,
`cost_latency_summary.csv`, `ratings_boxplots.png`, `paired_differences.png`, `analysis_meta.json`.

## Tests

```bash
PITCH_EVAL_MOCK=1 python -m tests.test_smoke
```

## Project structure

```
thesis-pitch-evaluator/
├── app.py                      Streamlit UI
├── config.py                   all experimental settings
├── agents/                     llm_client, base, single_agent, specialist (registry), ceo/cto/cfo/marketing_agent, moderator (3 stages)
├── prompts/                    shared fragments + one prompt module per agent
├── workflows/                  single_workflow, multi_workflow, common (record builder)
├── evaluation/                 run_experiments, consistency, rubric, blinding, analyse_results, metrics, llm_judge
├── utils/                      storage, validation, token_utils
├── tests/                      mock-LLM smoke tests
└── data/pitches | outputs | ratings
```
