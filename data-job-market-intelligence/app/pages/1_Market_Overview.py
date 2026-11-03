"""Filtered SQL analytics using the shared light dashboard components."""

import streamlit as st

from app.components.charts import heatmap, location_chart, role_chart, seniority_chart, skills_chart
from app.components.design import empty_state, kpi, panel
from app.components.ui import filters_panel, read, setup

setup("Market Overview", "Explore skills, roles and locations in historical job postings.")
st.caption(
    "Collected January 12–17, 2024 · Charts show recorded frequencies, not current hiring trends. "
    "All counts reflect the selected filters. A posting can mention several skills."
)
filters = filters_panel()
with st.spinner("Loading matching historical statistics…"):
    data = read("/api/analytics/overview", filters)
if data is None:
    st.stop()
if not data["total_jobs"]:
    empty_state(
        "No matching postings", "Broaden the country, role or other filters to explore the dataset."
    )
    st.stop()

classified = [r for r in data["by_job_title"] if r["name"] != "Other / Unclassified"]
with st.container(key="overview_kpis"):
    cols = st.columns(4, gap="medium")
values = [
    (
        "Matching Postings",
        f"{data['total_jobs']:,}",
        "Historical records matching your filters",
        "file",
    ),
    (
        "Top Skill",
        data["top_skills"][0]["name"] if data["top_skills"] else "Unavailable",
        "Most frequently mentioned tracked skill",
        "sparkles",
    ),
    (
        "Leading Tracked Role",
        classified[0]["name"] if classified else "Unavailable",
        "Unclassified titles are retained in the data",
        "workspace",
    ),
    (
        "Top Recorded City",
        next((r["name"] for r in data["by_city"] if r["name"] != "Unknown"), "Unknown"),
        "Based on recorded locations",
        "globe",
    ),
]
for column, (label, value, foot, name) in zip(cols, values, strict=True):
    with column:
        kpi(label, value, foot, name=name)

with st.container(key="overview_charts"):
    left, right = st.columns([1.2, 1], gap="medium")
with left:
    with panel("Top Skills in Demand", "overview_skills", "Counts and shares of matching jobs"):
        skills_chart(data["top_skills"], data["total_jobs"], limit=10)
    with panel("Job Distribution by Role", "overview_roles", "Includes unclassified source titles"):
        role_chart(data["by_job_title"], key="overview_roles", height=325, limit=10)
        st.caption(
            "Other / Unclassified: source titles outside the tracked role families. "
            "These postings remain included in totals."
        )
with right:
    with panel("Seniority Distribution", "overview_seniority", "Exact categories from the dataset"):
        seniority_chart(data["by_seniority"], data["total_jobs"], key="overview_seniority")
    with panel("Geographic Distribution", "overview_geo"):
        location_chart(data["by_country"], data["by_city"], key="overview_geo", compact=False)
    with panel("Workplace Type", "overview_workplace"):
        role_chart(data["by_workplace_type"], key="workplace", height=175)

with panel(
    "Skill × Role", "overview_matrix", "Matching postings mentioning a skill in each role family"
):
    roles = [r["name"] for r in data["by_job_title"][:6]]
    skills = [r["name"] for r in data["top_skills"][:8]]
    matrix = read(
        "/api/analytics/skill-role",
        {**filters, "roles": "|".join(roles), "skills": "|".join(skills)},
    )
    if matrix:
        heatmap(matrix["items"], roles, skills)

with st.expander("Dataset coverage and methodology"):
    st.caption(
        "Collection dates are not job publication dates. No monthly hiring trend is inferred."
    )
    if data["salary"]["groups"]:
        st.dataframe(data["salary"]["groups"], hide_index=True, width="stretch")
        st.caption(data["salary"]["note"])
    else:
        st.info("Comparable structured salaries are unavailable in this dataset.")
    if data["publication_trends"]["items"]:
        st.dataframe(data["publication_trends"]["items"], hide_index=True, width="stretch")
    else:
        st.info(
            "Publication dates are unavailable; monthly recruitment trends cannot be calculated."
        )
    unknown = next((r["count"] for r in data["by_city"] if r["name"] == "Unknown"), 0)
    st.caption(f"{unknown:,} matching postings have no recorded city.")
