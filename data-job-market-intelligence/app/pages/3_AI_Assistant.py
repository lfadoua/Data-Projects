"""Actual assistant responses, with a conversation and source-evidence panel."""

import streamlit as st

from app.components.design import empty_state, panel, section
from app.components.ui import filters_panel, render_answer, request, setup, sources_panel

setup("AI Assistant", "Ask a question. See the evidence behind the answer.")
filters = filters_panel()
st.session_state.setdefault("messages", [])
pending = st.session_state.pop("pending_question", None)
chosen = None

if st.session_state.messages:
    if st.button("Clear conversation", icon=":material/delete_sweep:"):
        st.session_state.messages = []
        st.rerun()
else:
    section(
        "From a question to an informed decision",
        "Counts use SQL. Descriptive answers cite selected job postings.",
    )
    examples = [
        "What are the top 10 most requested skills?",
        "What responsibilities are expected from Senior Data Engineers?",
        "How many Data Engineer jobs are in France?",
        "What skills are commonly associated with Kubernetes?",
    ]
    for offset in (0, 2):
        for column, example in zip(st.columns(2), examples[offset : offset + 2], strict=True):
            with column:
                if st.button(example, key=f"example_{offset}_{example}", width="stretch"):
                    chosen = example

conversation, evidence = st.columns([1.85, 1], gap="medium")
with conversation:
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                render_answer(message["content"], key=f"message_{i}", show_sources=False)

latest = next(
    (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None
)
with evidence:
    with panel("Source Evidence", "assistant_sources", "Inspect the most recent answer"):
        if latest and latest["route"] == "rag":
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
            empty_state(
                "Evidence appears here",
                "Ask a descriptive question to inspect its supporting job postings.",
            )

question = (
    pending
    or chosen
    or st.chat_input("Ask about roles, skills, requirements or counts…", max_chars=2000)
)
if question:
    if len(question.strip()) < 3:
        st.warning("Please enter a question with at least three characters.")
        st.stop()
    st.session_state.messages.append({"role": "user", "content": question})
    with conversation:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching relevant postings and checking the evidence…"):
                result = request(
                    "/api/assistant/query", body={"question": question, "filters": filters}
                )
            if result:
                st.session_state.messages.append({"role": "assistant", "content": result})
                st.rerun()
            else:
                st.info(
                    "Your question is saved above. You can retry it when the service reconnects."
                )
