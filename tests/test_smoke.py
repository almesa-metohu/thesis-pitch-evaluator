"""Smoke tests that run entirely with the mock LLM (no API calls).

Run with:  PITCH_EVAL_MOCK=1 python -m pytest -q   (or python -m tests.test_smoke)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("PITCH_EVAL_MOCK", "1")

import config  # noqa: E402
from agents.moderator import parse_addressees, parse_followup_questions  # noqa: E402
from agents.specialist import SPECIALIST_IDS  # noqa: E402
from evaluation.consistency import aggregate_pairs, pairwise_agreement  # noqa: E402
from prompts import FINAL_PITCH_USER_PROMPT, MODERATOR_SYSTEM_PROMPT, MODERATOR_USER_PROMPT, SINGLE_AGENT_SYSTEM_PROMPT  # noqa: E402
from prompts.shared import FINAL_LENGTH_INSTRUCTION, FINAL_LENGTH_REMINDER, FINAL_REPORT_STRUCTURE  # noqa: E402
from utils.storage import load_pitches  # noqa: E402
from utils.token_utils import count_tokens, count_words, estimate_cost_usd  # noqa: E402
from utils.validation import ValidationError, find_missing_sections, find_role_mentions, split_sections, validate_pitch_text  # noqa: E402
from workflows import run_multi_workflow, run_single_workflow  # noqa: E402


def test_both_final_prompts_share_template_and_length_budget() -> None:
    for prompt in (SINGLE_AGENT_SYSTEM_PROMPT, MODERATOR_SYSTEM_PROMPT):
        assert FINAL_REPORT_STRUCTURE in prompt
        assert FINAL_LENGTH_INSTRUCTION in prompt
    assert "Strategos" not in SINGLE_AGENT_SYSTEM_PROMPT + MODERATOR_SYSTEM_PROMPT
    assert FINAL_PITCH_USER_PROMPT.endswith(FINAL_LENGTH_REMINDER)
    assert MODERATOR_USER_PROMPT.endswith(FINAL_LENGTH_REMINDER)


def test_token_and_word_utils() -> None:
    assert count_words("one two-three four.") == 3
    assert count_tokens("hello world") > 0
    assert estimate_cost_usd(1_000_000, 0, "gpt-4o-mini") == 0.15
    assert estimate_cost_usd(10, 10, "unknown-model") == 0.0


def test_validation() -> None:
    try:
        validate_pitch_text("too short")
    except ValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("short pitch should fail")
    report = "\n".join(f"## {i}. {s}\nbody {i}" for i, s in enumerate(config.REPORT_SECTIONS, 1))
    assert find_missing_sections(report) == []
    assert split_sections(report)["Main Risks"] == "body 6"
    assert find_missing_sections("## Overall Assessment\nx") == list(config.REPORT_SECTIONS[1:])
    assert find_role_mentions("The pitch's savings figure is unvalidated.") == []
    assert find_role_mentions("The CFO's concern and the Moderator's view, per the panel.") == ["CFO", "Moderator", "panel"]
    assert find_role_mentions("ceo cto cfo lowercase acronyms are not flagged") == []


def test_workflows_produce_identical_record_schema() -> None:
    pitch = load_pitches()[0]
    single = run_single_workflow(pitch.pitch_text, pitch.pitch_id, pitch.title, 1, "test")
    multi = run_multi_workflow(pitch.pitch_text, pitch.pitch_id, pitch.title, 1, "test")
    required = {"pitch_id", "system_type", "run_number", "model", "temperature", "timestamp", "latency_seconds", "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd", "word_count", "token_count", "report"}
    assert required <= set(single) and required <= set(multi)
    assert single["max_output_tokens"] == multi["max_output_tokens"] == config.MAX_OUTPUT_TOKENS
    assert single["temperature"] == multi["temperature"]
    assert single["llm_calls"] == 1
    assert multi["llm_calls"] == len(multi["discussion"]) == multi["discussion_messages"]
    assert single["missing_sections"] == [] and multi["missing_sections"] == []
    assert single["role_mentions"] == [] and multi["role_mentions"] == []
    assert "discussion" not in single and "followup_questions" not in single
    # Both final reports share the same budget and cap regardless of discussion size.
    assert single["target_output_words"] == multi["target_output_words"] == config.TARGET_OUTPUT_WORDS
    # Multi totals must include the whole discussion, not just the final call.
    assert multi["total_tokens"] > multi["final_output_tokens"]


def test_discussion_structure() -> None:
    pitch = load_pitches()[0]
    multi = run_multi_workflow(pitch.pitch_text, pitch.pitch_id, pitch.title, 1, "test")
    d = multi["discussion"]
    rounds = [m["round"] for m in d]
    assert rounds == sorted(rounds), "discussion must be chronological"
    # Stage 0: moderator opening, no evaluation yet.
    assert d[0] == {**d[0], "round": 0, "agent": "moderator", "type": "opening"}
    # Round 1: exactly one analysis per specialist, in panel order.
    analyses = [m for m in d if m["type"] == "analysis"]
    assert [m["agent"] for m in analyses] == list(SPECIALIST_IDS)
    assert all(m["round"] == 1 for m in analyses)
    # Stage 2: one follow-up message with 2-4 questions, each to a subset of specialists.
    follow_ups = [m for m in d if m["type"] == "follow_up"]
    assert len(follow_ups) == 1 and follow_ups[0]["agent"] == "moderator"
    questions = multi["followup_questions"]
    assert questions == follow_ups[0]["questions"]
    assert config.MIN_FOLLOWUP_QUESTIONS <= len(questions) <= config.MAX_FOLLOWUP_QUESTIONS
    for q in questions:
        assert q["to"] and set(q["to"]) <= set(SPECIALIST_IDS) and q["question"]
    # Round 2: only addressed specialists respond, once each, and cite question ids.
    addressed = {a for q in questions for a in q["to"]}
    responses = [m for m in d if m["type"] == "response"]
    assert {m["agent"] for m in responses} == addressed
    assert len(responses) == len(addressed)
    for m in responses:
        assert m["round"] == 2 and m["question_ids"]
        assert all(m["agent"] in questions[i - 1]["to"] for i in m["question_ids"])
    # Final: moderator report is the last message and equals the record's report.
    assert d[-1]["agent"] == "moderator" and d[-1]["type"] == "final_report"
    assert d[-1]["content"] == multi["report"]
    # Every message carries measurements.
    for m in d:
        assert m["input_tokens"] > 0 and m["output_tokens"] > 0 and "latency_seconds" in m
    assert set(multi["per_agent_latency_seconds"]) == {f"{m['round']}_{m['agent']}_{m['type']}" for m in d}


def test_followup_question_parser() -> None:
    text = (
        "## Cross-Domain Issues\n- growth vs funding\n\n## Follow-up Questions\n"
        "### Question 1\nTo: CEO Agent, CFO Agent\nQuestion: How does the uncosted expansion\naffect viability?\n"
        "### Question 2\n**To:** CTO Agent and Sales/Marketing Agent\n**Question:** Does the API cost scale?\n"
        "### Question 3\nTo: Nobody in particular\nQuestion: ignored, no valid addressee\n"
    )
    qs = parse_followup_questions(text)
    assert [q["id"] for q in qs] == [1, 2]
    assert qs[0]["to"] == ["ceo", "cfo"] and qs[0]["question"].startswith("How does the uncosted expansion")
    assert qs[1]["to"] == ["cto", "marketing"]
    assert parse_addressees("the CFO Agent and the Sales team") == ["cfo", "marketing"]
    # Cap at MAX_FOLLOWUP_QUESTIONS.
    many = "".join(f"### Question {i}\nTo: CEO Agent\nQuestion: q{i}\n" for i in range(1, 8))
    assert len(parse_followup_questions(many)) == config.MAX_FOLLOWUP_QUESTIONS
    # Unparseable review falls back to one question for all four specialists.
    fallback = parse_followup_questions("free text without the required format")
    assert len(fallback) == 1 and fallback[0]["to"] == list(SPECIALIST_IDS) and fallback[0].get("parse_fallback")


def test_blinded_export_hides_discussion() -> None:
    import evaluation.blinding as blinding

    pitch = load_pitches()[0]
    single = run_single_workflow(pitch.pitch_text, pitch.pitch_id, pitch.title, 1, "blindtest")
    multi = run_multi_workflow(pitch.pitch_text, pitch.pitch_id, pitch.title, 1, "blindtest")
    original_loader, original_dir = blinding.load_all_runs, config.RATINGS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        blinding.load_all_runs = lambda subdir=None: [single, multi]
        config.RATINGS_DIR = tmp_path  # keep the secret key file out of data/ratings
        try:
            out = blinding.export_blinded("blindtest", 1, out_dir=tmp_path / "blinded", reviewer_ids=("R1",))
        finally:
            blinding.load_all_runs, config.RATINGS_DIR = original_loader, original_dir
        reports = sorted(out.glob("*_Report_*.md"))
        assert len(reports) == 2
        for path in reports:
            body = path.read_text(encoding="utf-8")
            assert body.count("## 1. Overall Assessment") == 1
            for leak in ("Response to Question", "Follow-up", "single-agent", "multi-agent"):
                assert leak not in body, f"{path.name} leaks '{leak}'"
            assert find_role_mentions(body) == [], f"{path.name} leaks role words"
        # The reviewer folder contains no JSON, no key and no discussion files.
        assert not list(out.glob("*.json")) and not (out / "blinding_key.csv").exists()
        assert (tmp_path / "blinding_key.csv").exists()


def test_agreement_metrics() -> None:
    a = "## 6. Main Risks\n- churn risk\n## 8. Prioritised Recommendations\n- validate pricing"
    b = "## 6. Main Risks\n- churn risk\n## 8. Prioritised Recommendations\n- validate pricing"
    m = pairwise_agreement(a, b)
    assert m["lexical_jaccard"] == 1.0 and m["risk_overlap"] == 1.0
    agg = aggregate_pairs([a, b, a])
    assert agg["lexical_jaccard"]["n_pairs"] == 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
