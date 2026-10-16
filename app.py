"""Minimal Streamlit UI for the thesis prototype.

Paste or select a pitch, choose a condition, run, and inspect the reports with
their measurements. Every run is saved to data/outputs like a batch run.
"""

from __future__ import annotations

import streamlit as st

import config
from utils.storage import load_pitches, save_run
from utils.validation import ValidationError
from workflows import run_multi_workflow, run_single_workflow

st.set_page_config(page_title="Pitch Evaluation Prototype", layout="wide")
st.title("Business Pitch Evaluation: Single-Agent vs Multi-Agent")
st.caption(
    f"Model: {config.MODEL_NAME} | temperature: {config.TEMPERATURE} | "
    f"max output tokens: {config.MAX_OUTPUT_TOKENS} | "
    f"target length: {config.TARGET_OUTPUT_WORDS} +/- {config.OUTPUT_TOLERANCE} words"
    + (" | MOCK LLM ACTIVE" if config.MOCK_LLM else "")
)

pitches = load_pitches()
options = ["(paste your own)"] + [f"{p.pitch_id} - {p.title}" for p in pitches]
choice = st.selectbox("Load a pitch from the dataset", options)
selected = pitches[options.index(choice) - 1] if choice != options[0] else None

pitch_text = st.text_area(
    "Business pitch",
    value=selected.pitch_text if selected else "",
    height=260,
    placeholder="Paste a business pitch here...",
)
mode = st.radio("System", ["Single-Agent", "Multi-Agent", "Compare Both"], horizontal=True)
run_clicked = st.button("Run Evaluation", type="primary")


def _show_report(title: str, record: dict) -> None:
    """Render one report with its metadata."""
    st.subheader(title)
    cols = st.columns(5)
    cols[0].metric("Latency (s)", f"{record['latency_seconds']:.2f}")
    cols[1].metric("Words", record["word_count"])
    cols[2].metric("Report tokens", record["token_count"])
    cols[3].metric("Total tokens (all calls)", record["total_tokens"])
    cols[4].metric("Est. cost (USD)", f"{record['estimated_cost_usd']:.4f}")
    flags = []
    if not record["within_length_budget"]:
        flags.append(f"outside length budget ({record['word_count']} words)")
    if record["missing_sections"]:
        flags.append("missing sections: " + ", ".join(record["missing_sections"]))
    if record.get("role_mentions"):
        flags.append("blinding risk, report mentions: " + ", ".join(record["role_mentions"]))
    if flags:
        st.warning("; ".join(flags))
    st.markdown(record["report"])


_ROUND_LABELS = {0: "Stage 0 - Moderator opening", 1: "Round 1 - Specialist analyses",
                 2: "Round 2 - Cross-domain follow-up", 3: "Final synthesis"}
_TYPE_LABELS = {"opening": "Opening", "analysis": "Round 1 analysis", "follow_up": "Follow-up questions",
                "response": "Round 2 response", "final_report": "Final report"}


def _show_discussion(record: dict) -> None:
    """Render the multi-agent panel discussion chronologically as a chat transcript.

    For inspection and demonstration only. Reviewer exports never include it.
    """
    st.subheader("Multi-Agent Discussion")
    st.caption(
        f"{record['discussion_messages']} messages, {record['llm_calls']} LLM calls, "
        f"{record['total_tokens']} tokens in total, wall-clock {record['latency_seconds']:.1f}s "
        f"(sequential {record['sequential_latency_seconds']:.1f}s). Not shown to human reviewers."
    )
    current_round = None
    for msg in record["discussion"]:
        if msg["round"] != current_round:
            current_round = msg["round"]
            st.markdown(f"**{_ROUND_LABELS.get(current_round, f'Round {current_round}')}**")
        is_moderator = msg["agent"] == "moderator"
        with st.chat_message("assistant" if is_moderator else "user"):
            suffix = ""
            if msg["type"] == "response":
                suffix = " to question(s) " + ", ".join(str(i) for i in msg.get("question_ids", []))
            st.markdown(
                f"**{msg['agent_label']}** - {_TYPE_LABELS.get(msg['type'], msg['type'])}{suffix}  \n"
                f"<small>{msg['word_count']} words, {msg['latency_seconds']:.1f}s, "
                f"{msg['input_tokens']} in / {msg['output_tokens']} out tokens</small>",
                unsafe_allow_html=True,
            )
            if msg["type"] == "final_report":
                st.caption("Shown in full in the comparison view above.")
            else:
                st.markdown(msg["content"])


if run_clicked:
    pitch_id = selected.pitch_id if selected else "adhoc"
    pitch_title = selected.title if selected else "Pasted pitch"
    systems = {
        "Single-Agent": [("Single-Agent report", run_single_workflow)],
        "Multi-Agent": [("Multi-Agent report (moderator)", run_multi_workflow)],
        "Compare Both": [
            ("Single-Agent report", run_single_workflow),
            ("Multi-Agent report (moderator)", run_multi_workflow),
        ],
    }[mode]
    records: list[tuple[str, dict]] = []
    try:
        for title, workflow in systems:
            with st.spinner(f"Running {title}..."):
                record = workflow(pitch_text, pitch_id, pitch_title, 1, "streamlit")
                save_run(record, "streamlit")
                records.append((title, record))
    except ValidationError as exc:
        st.error(str(exc))
    except RuntimeError as exc:
        st.error(str(exc))
    if len(records) == 2:
        left, right = st.columns(2)
        with left:
            _show_report(*records[0])
        with right:
            _show_report(*records[1])
    elif records:
        _show_report(*records[0])
    for _, record in records:
        if "discussion" in record:
            st.divider()
            _show_discussion(record)
