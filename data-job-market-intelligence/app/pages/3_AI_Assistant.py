"""Actual assistant responses, with a conversation and source-evidence panel."""

import inspect

import streamlit as st

from app.components.design import panel
from app.components.ui import (
    assistant_body,
    assistant_wait_message,
    filters_panel,
    render_answer,
    request,
    response_mode_selector,
    setup,
    sources_panel,
)
from app.components.voice_input import render_voice_input


def render_messages(messages, start=0):
    for i, message in enumerate(messages, start):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                render_answer(message["content"], key=f"message_{i}", show_sources=False)


setup("AI Assistant", "Ask a question. See the evidence behind the answer.")
filters = filters_panel()
mode_column, scope_column = st.columns([1, 1.85], vertical_alignment="bottom")
with mode_column:
    response_mode = response_mode_selector()
with scope_column:
    st.caption(
        "Historical postings · collected January 12–17, 2024. "
        "Selected evidence does not describe today's job market."
    )
st.session_state.setdefault("messages", [])
pending = st.session_state.pop("pending_question", None)
chosen = None
retry_body = None

if st.session_state.messages:
    if st.button("Clear conversation", icon=":material/delete_sweep:"):
        st.session_state.messages = []
        st.session_state.pop("assistant_failed_request", None)
        st.rerun()

with st.container(key="assistant_workspace"):
    conversation, evidence = st.columns([1.85, 1], gap="medium")
with conversation:
    with panel("Ask a question", "assistant_compose", "Type below or choose an example"):
        inline_microphone = "accept_audio" in inspect.signature(st.chat_input).parameters
        entry_options = {"max_chars": 2000}
        if inline_microphone:
            entry_options.update(accept_audio=True, audio_sample_rate=16000)
        entry = st.chat_input("Ask about roles, skills, requirements or counts…", **entry_options)
        if inline_microphone:
            audio = getattr(entry, "audio", None)
            text = entry if isinstance(entry, str) else getattr(entry, "text", "")
            entered = None if audio is not None else text
            voice_question = render_voice_input(audio, native_capture=True, prefix=text or "")
        else:
            entered = entry
            voice_question = render_voice_input()
        st.caption(
            "Press Enter to send · Shift + Enter for a new line. "
            "Filters apply to new questions. Microphone: English."
        )
        with st.expander("How are answers produced?"):
            st.write("**SQL Analytics** calculates counts and percentages from structured records.")
            st.write("**RAG** finds passages in historical job descriptions to support an answer.")
            st.write(
                "**[S1], [S2]** identify cited postings. Open Source Evidence to read the text."
            )
        if not st.session_state.messages:
            st.caption(
                "Try a question · counts use SQL; responsibilities and requirements use RAG."
            )
            examples = [
                "What are the top 10 most requested skills?",
                "What responsibilities are expected from Senior Data Engineers?",
                "How many Data Engineer jobs are in France?",
                "What skills are commonly associated with Kubernetes?",
            ]
            for offset in (0, 2):
                for column, example in zip(
                    st.columns(2), examples[offset : offset + 2], strict=True
                ):
                    with column:
                        if st.button(example, key=f"example_{offset}_{example}", width="stretch"):
                            chosen = example
    if st.session_state.get("assistant_failed_request"):
        st.warning("The last request could not be completed. Your question has been kept.")
        if st.button("Retry last question", icon=":material/refresh:"):
            retry_body = st.session_state["assistant_failed_request"]
        st.caption(
            "Retry uses the same question, filters and response mode. No automatic retry occurs."
        )
    latest_question = max(
        (i for i, m in enumerate(st.session_state.messages) if m["role"] == "user"), default=0
    )
    if latest_question:
        with st.expander("Earlier questions and answers"):
            render_messages(st.session_state.messages[:latest_question])
    render_messages(st.session_state.messages[latest_question:], start=latest_question)

latest = next(
    (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None
)
with evidence:
    with panel("Source Evidence", "assistant_sources", "Inspect the most recent answer"):
        if latest and latest["route"] == "rag":
            st.caption("[S1] and [S2] link claims to the original posting text below.")
            sources_panel(latest, expanded_first=True)
            st.caption(
                "Source IDs belong to this answer. Counts describe selected evidence, "
                "not the whole market."
            )
        elif latest:
            st.info("This is a SQL analytics answer. No retrieved job sources are required.")
            if latest.get("metadata", {}).get("filters"):
                st.json(latest["metadata"]["filters"])
        else:
            st.write("Your supporting sources will appear here after a descriptive question.")
            st.caption(
                "Each citation, such as [S1], points to a job posting you can inspect. "
                "Questions about counts use SQL and do not need retrieved passages."
            )

question = retry_body["question"] if retry_body else pending or chosen or entered or voice_question
if question:
    if len(question.strip()) < 3:
        st.warning("Please enter a question with at least three characters.")
        st.stop()
    body = retry_body or assistant_body(question, filters, response_mode)
    if not retry_body:
        st.session_state.messages.append({"role": "user", "content": question})
    with conversation:
        if not retry_body:
            with st.chat_message("user"):
                st.write(question)
        with st.chat_message("assistant"):
            with st.spinner(assistant_wait_message(body.get("response_mode"))):
                result = request("/api/assistant/query", body=body)
            if result:
                st.session_state.pop("assistant_failed_request", None)
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
            else:
                st.session_state["assistant_failed_request"] = body
                st.rerun()
