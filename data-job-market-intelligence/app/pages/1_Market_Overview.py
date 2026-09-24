"""SQL-backed market view with consistent charts and honest coverage states."""

import plotly.graph_objects as go
import streamlit as st

from app.components.design import chips, empty_state, kpi, section
from app.components.ui import bar, filters_panel, read, setup

setup("Market Overview", "Explore skills, roles and hiring patterns across real job postings.")
filters = filters_panel()
if filters:
    chips(
        [f"{key.replace('_', ' ').title()}: {value}" for key, value in filters.items()],
        neutral=True,
    )
data = read("/api/analytics/overview", filters)
if data is None:
    st.stop()
if not data["total_jobs"]:
    empty_state(
        "No matching postings",
        "Broaden one or more filters in the sidebar to see this market view.",
    )
    st.stop()

columns = st.columns(4, gap="medium")
classified_roles = [item for item in data["by_job_title"] if item["name"] != "Other / Unclassified"]
for column, label, value, foot in [
    (columns[0], "Total jobs", f"{data['total_jobs']:,}", "Matching postings"),
    (
        columns[1],
        "Top skill",
        data["top_skills"][0]["name"] if data["top_skills"] else "Unavailable",
        "Tracked skill mentions",
    ),
    (
        columns[2],
        "Leading tracked role",
        classified_roles[0]["name"] if classified_roles else "Unavailable",
        "Excludes unclassified titles",
    ),
    (
        columns[3],
        "Top location",
        data["by_city"][0]["name"] if data["by_city"] else "Unavailable",
        "Recorded city",
    ),
]:
    with column:
        kpi(label, value, foot)

left, right = st.columns(2, gap="large")
with left:
    bar(data["top_skills"], "Most requested tracked skills")
    bar(data["by_seniority"], "Seniority distribution")
    bar(data["by_country"], "Geographic distribution")
with right:
    bar(data["by_job_title"], "Jobs by role family")
    bar(data["by_workplace_type"], "Work arrangement")
    bar(data["by_city"][:10], "Leading cities")

section(
    "Skill × role",
    "Number of matching postings that mention each tracked skill within each role family.",
)
roles = [item["name"] for item in data["by_job_title"][:6]]
skills = [item["name"] for item in data["top_skills"][:8]]
matrix = read(
    "/api/analytics/skill-role", {**filters, "roles": "|".join(roles), "skills": "|".join(skills)}
)
if matrix and matrix["items"]:
    values = {(item["role"], item["skill"]): item["count"] for item in matrix["items"]}
    figure = go.Figure(
        data=go.Heatmap(
            z=[[values.get((role, skill), 0) for skill in skills] for role in roles],
            x=skills,
            y=roles,
            colorscale=[[0, "#eff4fc"], [0.4, "#8eb8f1"], [1, "#285cdb"]],
            hovertemplate="%{y} · %{x}<br>%{z:,} postings<extra></extra>",
            colorbar={"title": "Postings"},
        )
    )
    figure.update_layout(
        height=max(350, 62 * len(roles)),
        margin=dict(l=0, r=0, t=12, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, sans-serif", "color": "#40536e"},
    )
    st.plotly_chart(figure, width="stretch")
else:
    empty_state(
        "No role–skill overlap", "The selected filters contain no tracked combinations to display."
    )

with st.expander("Salary and publication-date coverage"):
    if data["salary"]["groups"]:
        st.caption(data["salary"]["note"])
        st.dataframe(data["salary"]["groups"], hide_index=True, width="stretch")
    else:
        st.info("Data not available in this dataset: comparable structured salaries.")
    if data["publication_trends"]["items"]:
        st.dataframe(data["publication_trends"]["items"], hide_index=True, width="stretch")
    else:
        st.info("Data not available in this dataset: publication dates for a hiring time series.")
