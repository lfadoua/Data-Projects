"""Filterable posting cards with provenance and clear empty states."""

import streamlit as st

from app.components.design import chips, empty_state, safe, section
from app.components.ui import filters_panel, read, setup

PAGE_SIZE = 12

setup(
    "Job Explorer", "Find the postings behind the patterns. Filter, inspect and follow the source."
)
filters = filters_panel()
if filters:
    chips(
        [f"{key.replace('_', ' ').title()}: {value}" for key, value in filters.items()],
        neutral=True,
    )
summary = read("/api/analytics/skills", {**filters, "limit": 1})
if summary is None:
    st.stop()
total = summary["total_jobs"]
section(
    f"{total:,} jobs found",
    "Results are records from the historical snapshot; each card links to its original "
    "source when available.",
)
if not total:
    empty_state(
        "No jobs match these filters",
        "Try removing a filter or selecting a broader role or location.",
    )
    st.stop()
max_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
page = st.number_input("Results page", min_value=1, max_value=max_page, value=1, step=1)
data = read(
    "/api/analytics/jobs", {**filters, "limit": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE}
)
if data is None:
    st.stop()
st.caption(
    f"Showing {(page - 1) * PAGE_SIZE + 1:,}–{min(page * PAGE_SIZE, total):,} of {total:,} postings"
)
for job in data["items"]:
    with st.container(border=True):
        st.markdown(
            f'<div class="dj-job-head">{safe(job["job_title"])}</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="dj-job-meta">'
            + " · ".join(
                safe(part)
                for part in (
                    job.get("company") or "Company not listed",
                    job.get("location") or "Location not listed",
                    job.get("seniority") or "Seniority not listed",
                    job.get("workplace_type") or "Workplace not listed",
                )
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        if job.get("skills"):
            shown = job["skills"][:9]
            chips(shown + ([f"+{len(job['skills']) - 9} more"] if len(job["skills"]) > 9 else []))
        else:
            st.caption("No tracked skills detected in this posting.")
        with st.expander("Read job description"):
            st.write(job.get("cleaned_description") or "No description provided.")
        url = job.get("source_url") or ""
        if url.startswith(("http://", "https://")):
            st.link_button("View original posting ↗", url)
        else:
            st.caption(f"Source: {job.get('source') or 'Unknown'} · Original link unavailable")
