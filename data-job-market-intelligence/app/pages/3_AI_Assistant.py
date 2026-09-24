"""Evidence-first assistant chat. Every response comes from FastAPI."""

import streamlit as st

from app.components.design import chips, section
from app.components.ui import filters_panel, render_answer, request, setup

EXAMPLES = [
    "What skills are most requested for Data Engineers?",
    "What do Senior Data Engineers typically work on?",
    "How many Data Engineer jobs are in France?",
    "What technologies appear with Kubernetes?",
]

setup("Ask the Job Market", "Ask questions across real job postings and structured market data.")
filters = filters_panel()
if filters:
    chips(
        [f"{key.replace('_', ' ').title()}: {value}" for key, value in filters.items()],
        neutral=True,
    )
st.caption(
    "Quantitative answers use SQL. Descriptive answers cite retrieved postings from the "
    "historical dataset."
)
if "messages" not in st.session_state:
    st.session_state.messages = []

chosen = None
if not st.session_state.messages:
    section("Start with a question", "Try an example or ask your own question below.")
    example_columns = st.columns(2, gap="small")
    for index, example in enumerate(EXAMPLES):
        with example_columns[index % 2]:
            if st.button(example, key=f"example_{index}", width="stretch"):
                chosen = example
else:
    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            render_answer(message["content"])

question = chosen or st.chat_input(
    "Ask about roles, skills, requirements or counts…", max_chars=2000
)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching the dataset and checking the evidence…"):
            result = request(
                "/api/assistant/query", body={"question": question, "filters": filters}
            )
        if result:
            st.session_state.messages.append({"role": "assistant", "content": result})
            st.rerun()
        else:
            st.info(
                "The answer is unavailable right now. Check the backend connection and try again."
            )
