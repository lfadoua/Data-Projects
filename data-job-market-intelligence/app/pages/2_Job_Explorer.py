"""Searchable, filterable historical job cards with real source links."""

import streamlit as st

from app.components.design import chips, empty_state, panel, safe, section
from app.components.preferences import preferences
from app.components.ui import filters_panel, read, setup

setup(
    "Job Explorer",
    "Discover and explore data and AI opportunities from the historical job dataset.",
)
filters = filters_panel()
search = st.session_state.get("jobs_search", "")
if "explorer_query" not in st.session_state or st.session_state.get("explorer_seed") != search:
    st.session_state["explorer_query"] = search
    st.session_state["explorer_seed"] = search

with st.form("explorer_search", border=False):
    field, submit = st.columns([8, 1], gap="small", vertical_alignment="bottom")
    with field:
        query = st.text_input(
            "Search job titles, companies and descriptions",
            key="explorer_query",
            placeholder="e.g. Python, Data Engineer, or a company",
            max_chars=200,
            icon=":material/search:",
        )
    with submit:
        submitted = st.form_submit_button("Search", width="stretch", type="primary")
if submitted:
    st.session_state["jobs_search"] = query.strip()
    st.session_state["jobs_page"] = 1
    st.rerun()

page_size = preferences()["jobs_page_size"]
page = st.session_state.setdefault("jobs_page", 1)
params = {**filters, "limit": page_size, "offset": (page - 1) * page_size}
if search:
    params["search"] = search
data = read("/api/analytics/jobs", params)
if data is None:
    st.stop()
total = data["total"]
section(
    f"{total:,} jobs found",
    "Historical postings · source links may no longer be accepting applications.",
)
if search:
    chips([f"Search: {search}"], neutral=True)
if not total:
    empty_state("No matching jobs", "Try a broader search or remove one of the selected filters.")
    if st.button("Clear search"):
        st.session_state["jobs_search"] = ""
        st.session_state["jobs_page"] = 1
        st.rerun()
    st.stop()
max_page = max(1, (total + page_size - 1) // page_size)
if page > max_page:
    st.session_state["jobs_page"] = 1
    st.rerun()


def change_page(value):
    st.session_state["jobs_page"] = value


with st.container(key="jobs_pagination"):
    info, prev, number, nxt = st.columns([5.7, 1, 1.25, 1], vertical_alignment="center")
    with info:
        st.caption(
            f"Showing {(page - 1) * page_size + 1:,}–{min(page * page_size, total):,} "
            f"of {total:,} postings · page {page} of {max_page}"
        )
    with prev:
        st.button("← Previous", disabled=page <= 1, on_click=change_page, args=(page - 1,))
    with number:
        st.number_input(
            "Results page",
            min_value=1,
            max_value=max_page,
            step=1,
            key="jobs_page",
            label_visibility="collapsed",
        )
    with nxt:
        st.button("Next →", disabled=page >= max_page, on_click=change_page, args=(page + 1,))

for start in range(0, len(data["items"]), 2):
    columns = st.columns(2, gap="medium")
    for column, job in zip(columns, data["items"][start : start + 2]):
        with column:
            with panel("", f"job_{job['id']}"):
                st.html(
                    f'<div class="dj-job-head">{safe(job["job_title"])}</div>'
                    '<div class="dj-job-company">'
                    f"{safe(job.get('company') or 'Company not listed')}</div>"
                    '<div class="dj-job-meta">'
                    + " · ".join(
                        safe(v)
                        for v in [
                            job.get("location") or "Location not listed",
                            job.get("seniority") or "Seniority not listed",
                            job.get("workplace_type") or "Workplace not listed",
                        ]
                    )
                    + "</div>"
                )
                if job.get("skills"):
                    shown = job["skills"][:8]
                    chips(
                        shown
                        + ([f"+{len(job['skills']) - 8} more"] if len(job["skills"]) > 8 else [])
                    )
                else:
                    st.caption("No tracked skills detected in this posting.")
                description = job.get("cleaned_description") or ""
                size = 150 if preferences()["compact_jobs"] else 280
                preview = (
                    description[:size].rsplit(" ", 1)[0] + "…"
                    if len(description) > size
                    else description
                )
                st.html(f'<div class="dj-job-preview">{safe(preview)}</div>')
                with st.expander("Read full job description"):
                    st.write(description or "No description provided.")
                url = job.get("source_url") or ""
                if url.startswith(("https://", "http://")):
                    st.link_button("Original posting ↗", url, width="stretch")
                else:
                    st.caption("Original source link unavailable.")
