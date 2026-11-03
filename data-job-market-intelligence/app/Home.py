"""Interactive historical-market dashboard with evidence-backed assistant preview."""

import streamlit as st

from app.components.charts import location_chart, role_chart, seniority_chart, skills_chart
from app.components.dashboard import home_metrics, index_status, preview_card
from app.components.design import empty_state, panel
from app.components.ui import active_filters, read, setup

setup(
    "Data Job Market Intelligence",
    "Explore data and AI job postings collected January 12–17, 2024, "
    "with analytics and cited answers.",
    active="Home",
    home=True,
)
filters = active_filters()
overview = read("/api/analytics/overview", filters, quiet=True)
index = read("/api/system/status", quiet=True)
home_metrics(overview, index)

if overview is None:
    empty_state("The data service is reconnecting", "Charts will return when the API is available.")
elif not overview["total_jobs"]:
    empty_state(
        "No matching postings", "Choose another country or reset the filters in Market Overview."
    )
else:
    with st.container(key="home_charts"):
        skills, location, seniority = st.columns([1.12, 1.22, 1], gap="medium")
        with skills:
            with panel(
                "Top Skills in Demand", "home_skills", action=("View all", "/Market_Overview")
            ):
                skills_chart(overview["top_skills"], overview["total_jobs"])
                st.caption("Hover a skill for its count and share of matching postings.")
        with location:
            with panel("", "home_location"):
                location_chart(
                    overview["by_country"],
                    overview["by_city"],
                    key="home_map",
                    heading="Job Distribution by Location",
                )
        with seniority:
            with panel("Seniority Distribution", "home_seniority"):
                seniority_chart(
                    overview["by_seniority"], overview["total_jobs"], key="home_seniority"
                )

with st.container(key="home_lower"):
    roles, system, assistant = st.columns([1.3, 0.98, 1.42], gap="medium")
    with roles:
        with panel(
            "Job Distribution by Role", "home_roles", "Historical snapshot · not a hiring trend"
        ):
            if overview and overview["total_jobs"]:
                role_chart(overview["by_job_title"], key="home_roles", height=188, limit=6)
            else:
                st.caption("Role statistics are currently unavailable.")
    with system:
        with panel("V2 Index Status", "home_index"):
            index_status(index)
    with assistant:
        with panel("AI Assistant", "home_preview", "Grounded insights from selected postings"):
            preview_card(filters, index)

st.caption(
    "Historical dataset · collected January 12–17, 2024 · "
    "missing publication dates are not estimated."
)
