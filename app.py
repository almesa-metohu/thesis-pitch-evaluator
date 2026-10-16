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

st.set_page_config(
    page_title="PitchLab | LLM Evaluation Study",
    page_icon="◫",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container {max-width: 1450px; padding-top: 2rem; padding-bottom: 4rem;}
[data-testid="stSidebar"] {border-right: 1px solid rgba(120,120,120,.16);}
.hero {padding: .25rem 0 1.4rem 0;}
.eyebrow {font-size: .76rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; opacity: .55;}
.hero h1 {margin: .15rem 0 0 0; font-size: clamp(2rem,4vw,3.5rem); line-height: 1.05; letter-spacing: -.045em;}
.hero p {max-width: 760px; font-size: 1.02rem; opacity: .7; margin-top: .7rem;}
.badge {display:inline-block; border:1px solid rgba(120,120,120,.22); border-radius:999px; padding:.3rem .65rem; font-size:.78rem; opacity:.68;}
.section-label {font-size:.76rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700; opacity:.52; margin:.4rem 0 .8rem 0;}
div[data-testid="stMetric"] {border:1px solid rgba(120,120,120,.16); border-radius:12px; padding:.65rem .75rem;}
div[data-testid="stChatMessage"] {border:1px solid rgba(120,120,120,.14); border-radius:14px; margin-bottom:.6rem;}
.stTabs [data-baseweb="tab"] {border-radius:999px; padding-left:1rem; padding-right:1rem;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Experiment")
    st.caption("Controlled MSc research prototype")
    st.markdown("**Model**")
    st.code(config.MODEL_NAME, language=None)
    a, b = st.columns(2)
    a.metric("Temperature", config.TEMPERATURE)
    b.metric("Top-p", config.TOP_P)
    st.markdown("**Final report control**")
    st.caption(
        f"{config.TARGET_OUTPUT_WORDS} ± {config.OUTPUT_TOLERANCE} words · "
        f"{config.MAX_OUTPUT_TOKENS} token cap"
    )
    if config.MOCK_LLM:
        st.warning("Mock LLM active")
    st.divider()
    st.caption("Both conditions use the same final report template, model settings and length budget.")

st.markdown(
    f"""
    <div class="hero">
      <div class="eyebrow">MSc Artificial Intelligence · Research Prototype</div>
      <h1>Business Pitch Evaluation</h1>
      <p>Compare a strong single-agent evaluator with a moderated panel of specialised LLM agents under controlled experimental conditions.</p>
      <span class="badge">{config.MODEL_NAME} · controlled comparison</span>
    </div>
    """,
    unsafe_allow_html=True,
)

pitches = load_pitches()
options = ["(paste your own)"] + [f"{p.pitch_id} - {p.title}" for p in pitches]
st.markdown('<div class="section-label">01 · Input</div>', unsafe_allow_html=True)
input_left, input_right = st.columns([1.05, 2.15], gap="large")

with input_left:
    choice = st.selectbox("Pitch source", options)
    selected = pitches[options.index(choice) - 1] if choice != options[0] else None
    mode = st.radio(
        "Evaluation mode",
        ["Single-Agent", "Multi-Agent", "Compare Both"],
        index=2,
    )
    st.caption("Use Compare Both for the thesis experiment. The internal panel discussion is for inspection only.")

with input_right:
    pitch_text = st.text_area(
        "Business pitch",
        value=selected.pitch_text if selected else "",
        height=300,
        placeholder="Paste a business pitch here...",
    )

run_clicked = st.button(
    "Run evaluation",
    type="primary",
    use_container_width=True,
    disabled=not pitch_text.strip(),
)


def _show_report(title: str, record: dict) -> None:
    """Render one report with its metadata."""
    st.markdown(f"### {title}")
    st.caption("Final reviewer-facing report")
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
    st.markdown("### Expert panel discussion")
    st.caption("Internal multi-agent transcript for inspection only. It is never included in reviewer-facing blinded reports.")
    overview = st.columns(4)
    overview[0].metric("Messages", record["discussion_messages"])
    overview[1].metric("LLM calls", record["llm_calls"])
    overview[2].metric("Total tokens", record["total_tokens"])
    overview[3].metric("Wall-clock", f"{record['latency_seconds']:.1f}s")
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
    st.divider()
    st.markdown('<div class="section-label">02 · Results</div>', unsafe_allow_html=True)
    multi_record = next((r for _, r in records if "discussion" in r), None)

    if multi_record:
        report_tab, discussion_tab = st.tabs(["Final report(s)", "Multi-Agent discussion"])
    else:
        report_tab = st.container()
        discussion_tab = None

    with report_tab:
        if len(records) == 2:
            st.markdown("### Side-by-side comparison")
            st.caption("Same final structure and output-length budget for both conditions.")
            left, right = st.columns(2, gap="large")
            with left:
                _show_report(*records[0])
            with right:
                _show_report(*records[1])
        elif records:
            _show_report(*records[0])

    if discussion_tab is not None:
        with discussion_tab:
            _show_discussion(multi_record)
