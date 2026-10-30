# Appendix: Reproducibility Materials

This appendix documents the artefacts used to reproduce and inspect the thesis experiment.

## A.1 Repository and implementation structure

Repository: https://github.com/almesa-metohu/thesis-pitch-evaluator

Key implementation files:

- `agents/single_agent.py` - single-agent baseline.
- `agents/ceo_agent.py` - CEO specialist.
- `agents/cto_agent.py` - CTO specialist.
- `agents/cfo_agent.py` - CFO specialist.
- `agents/marketing_agent.py` - Sales/Marketing specialist.
- `agents/moderator.py` - moderator logic and follow-up routing.
- `workflows/single_workflow.py` - single-agent execution flow.
- `workflows/multi_workflow.py` - moderated multi-agent workflow.
- `config.py` - shared experimental configuration.
- `app.py` - Streamlit research interface.

## A.2 Prompt definitions

The complete prompt definitions are retained in the repository:

- `prompts/single_agent_prompt.py`
- `prompts/ceo_prompt.py`
- `prompts/cto_prompt.py`
- `prompts/cfo_prompt.py`
- `prompts/marketing_prompt.py`
- `prompts/moderator_prompt.py`
- `prompts/shared.py`

The multi-agent workflow uses four role-specific specialist prompts and three moderator stages: opening/framing, cross-domain follow-up, and final synthesis.

## A.3 Automated evaluator and rubric

The automated report-quality evaluator and scoring criteria are retained in:

- `evaluation/automated_judge.py`
- `evaluation/llm_judge.py`
- `evaluation/rubric.py`
- `evaluation/blinding.py`

The evaluator receives the original pitch and anonymised Report A / Report B outputs in randomised order. Specificity is scored on a 1-5 scale and analytical depth is scored independently for strategy, technology, finance, and sales/marketing on a 0-3 scale.

## A.4 Experimental outputs and logs

Main experiment outputs:

- `thesis_results/main_runs/`
- `thesis_results/main_runs_summary.csv`

Automated evaluation outputs:

- `thesis_results/automated_evaluation/automated_judge_results.csv`
- `thesis_results/automated_evaluation/automated_judge_results.json`

Stability outputs:

- `thesis_results/stability/stability_results.json`
- `thesis_results/stability/stability_summary.csv`

Derived reporting statistics:

- `thesis_results/derived_reporting_statistics.csv`
- `evaluation/derive_reporting_statistics.py`

The derivation script reproduces the pooled stability means and sample standard deviations reported in the thesis, together with mean and sample standard deviation for sequential latency.

## A.5 Worked example: P01 FleetSense

Pitch P01 was evaluated once by each system in the main experiment.

Single-agent run:
- Run ID: `39fa10536894`
- Final report length: 946 words
- Total tokens: 2,759
- Wall-clock latency: 12.89 s
- Sequential latency: 12.89 s
- LLM calls: 1
- Estimated API cost: USD 0.000973
- Full record: `thesis_results/main_runs/P01_single_r01_39fa10536894.json`

Multi-agent run:
- Run ID: `acb082258242`
- Final report length: 925 words
- Total tokens: 57,287
- Wall-clock latency: 70.725 s
- Sequential latency: 124.458 s
- LLM calls: 13
- Estimated API cost: USD 0.012991
- Full record: `thesis_results/main_runs/P01_multi_r01_acb082258242.json`

The full JSON records preserve the final reports, model settings, token usage, latency, LLM call count, cost estimate, output validation state, and other experiment metadata. The multi-agent record also preserves the internal moderated discussion used to generate the final report.

## A.6 Stability study

The repeated-run stability study used P01, P04, and P06. Each pitch was evaluated five times by each system under the same model settings.

This produced 30 final reports in total:

3 pitches x 2 systems x 5 runs = 30 reports.

For each pitch-system condition, the five runs create 10 unique pairwise report comparisons. Across three pitches, each system therefore contributes 30 pairwise comparisons for every stability metric.

The reported aggregate values are:

| Stability metric | Single mean | Single SD | Multi mean | Multi SD |
|---|---:|---:|---:|---:|
| Risk overlap | 0.3019 | 0.0862 | 0.2234 | 0.0605 |
| Recommendation overlap | 0.2636 | 0.0937 | 0.1644 | 0.0966 |
| Lexical Jaccard | 0.5149 | 0.0290 | 0.4346 | 0.0182 |
| Section-level Jaccard | 0.3903 | 0.0314 | 0.2867 | 0.0242 |
| Sequence similarity | 0.2298 | 0.0665 | 0.1304 | 0.0353 |

Sample standard deviation is used.

## A.7 Computational timing

The six main runs per system produced the following sequential latency values:

- Single-agent mean sequential latency: 11.264 s (SD = 1.535 s).
- Multi-agent mean sequential latency: 98.241 s (SD = 19.427 s).

Wall-clock latency is lower than sequential latency for the multi-agent workflow because the four Round 1 specialist analyses can run concurrently.

## A.8 Reproduction commands

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the Streamlit interface:

```bash
streamlit run app.py
```

Run the main comparison:

```bash
python -m evaluation.run_experiments --systems single multi --runs 1 --experiment main
```

Run the stability experiment:

```bash
python -m evaluation.consistency stability --pitch-ids P01 P04 P06
```

Reproduce the derived reporting statistics:

```bash
python -m evaluation.derive_reporting_statistics
```

## A.9 Interface evidence for the dissertation

The dissertation should include two screenshots from the implemented Streamlit interface:

1. the main input/evaluation screen; and
2. the Compare Both view showing the single-agent and multi-agent final reports side by side.

These screenshots document the implemented research prototype and should be included as appendix figures in the submitted dissertation PDF.
