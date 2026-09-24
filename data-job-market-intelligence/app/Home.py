"""Landing page for the historical job-market intelligence application."""

import streamlit as st

from app.components.design import kpi, section
from app.components.ui import read, setup

setup(
    "Data Job Market Intelligence",
    "Explore skills, roles and hiring patterns across real job postings.",
)
status = read("/health")
if status:
    first, second, third = st.columns(3, gap="medium")
    with first:
        kpi("Job postings", f"{status['jobs']:,}", "Source records loaded")
    with second:
        kpi("Evidence chunks", f"{status['chunks']:,}", "Searchable description passages")
    with third:
        kpi(
            "Evidence search",
            "Ready" if status["index_ready"] else "Unavailable",
            "Local semantic index",
        )

section("Choose a workspace", "Each view connects to the same historical posting dataset.")
left, middle, right = st.columns(3, gap="large")
with left:
    with st.container(border=True):
        st.subheader("Market Overview")
        st.write(
            "See the roles, skills, locations and work arrangements represented in the dataset."
        )
        st.page_link("pages/1_Market_Overview.py", label="Open dashboard →")
with middle:
    with st.container(border=True):
        st.subheader("Job Explorer")
        st.write("Narrow the records by role, geography, company, seniority and skill.")
        st.page_link("pages/2_Job_Explorer.py", label="Explore postings →")
with right:
    with st.container(border=True):
        st.subheader("AI Assistant")
        st.write("Ask a question and trace descriptive answers back to source postings.")
        st.page_link("pages/3_AI_Assistant.py", label="Ask the market →")

section("How to read the results")
st.info(
    "Counts and rankings come from SQL. Descriptive answers summarize retrieved posting "
    "evidence. This is a historical dataset, not a live hiring feed."
)
quality = read("/api/analytics/quality")
if quality:
    with st.expander("Data quality and methodology"):
        st.json({key: value for key, value in quality.items() if key != "source_files"})
