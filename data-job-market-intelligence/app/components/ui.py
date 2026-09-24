"""HTTP-only UI helpers; no SQL or retrieval logic in Streamlit."""

import os
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import dotenv_values

from app.components.design import chips, empty_state, section, shell

ROOT = Path(__file__).resolve().parents[2]


def setup(title, subtitle="Explore skills, roles and hiring patterns across real job postings."):
    shell(title, subtitle, request)


def api_url():
    values = dotenv_values(ROOT / ".env", interpolate=False)
    return (
        os.getenv("STREAMLIT_API_URL") or values.get("STREAMLIT_API_URL") or "http://127.0.0.1:8000"
    ).rstrip("/")


def request(path, params=None, body=None, quiet=False):
    try:
        with httpx.Client(timeout=150 if body else 40) as client:
            response = (
                client.post(api_url() + path, json=body)
                if body is not None
                else client.get(api_url() + path, params=params)
            )
        if response.is_error:
            detail = response.json().get("detail", "The request could not be completed.")
            if not quiet:
                st.error(
                    detail
                    if isinstance(detail, str)
                    else "Check your question and selected filters."
                )
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        if not quiet:
            st.error("Cannot reach the backend. Start FastAPI and check STREAMLIT_API_URL.")
        return None


@st.cache_data(ttl=60, show_spinner=False)
def cached_get(url, path, items=()):
    response = httpx.get(url + path, params=dict(items), timeout=60)
    response.raise_for_status()
    return response.json()


def read(path, params=None):
    try:
        return cached_get(api_url(), path, tuple(sorted((params or {}).items())))
    except (httpx.HTTPError, ValueError):
        empty_state(
            "Data is temporarily unavailable",
            "Check that FastAPI and the database are running, then refresh this page.",
        )
        return None


@st.cache_data(ttl=60)
def get_facets(url):
    response = httpx.get(url + "/api/analytics/filters", timeout=40)
    response.raise_for_status()
    return response.json()


def filters_panel():
    try:
        facets = get_facets(api_url())
    except (httpx.HTTPError, ValueError):
        st.warning("Filters are unavailable until the backend database is connected.")
        return {}
    filters = {}
    with st.sidebar:
        st.markdown("### Refine results")
        for field, label in [
            ("job_title", "Job family"),
            ("country", "Country"),
            ("city", "City"),
            ("seniority", "Seniority"),
            ("workplace_type", "Workplace"),
            ("company", "Company"),
            ("skill", "Skill"),
        ]:
            chosen = st.selectbox(label, ["All"] + facets.get(field, []), key="filter_" + field)
            if chosen != "All":
                filters[field] = chosen
    return filters


def bar(items, title):
    section(title)
    if not items:
        st.caption("No matching data.")
        return
    frame = pd.DataFrame(items)
    figure = px.bar(
        frame,
        x="count",
        y="name",
        orientation="h",
        color_discrete_sequence=["#285cdb"],
        hover_data={"name": False, "count": ":,"},
    )
    figure.update_layout(
        yaxis={"categoryorder": "total ascending", "title": None, "tickfont": {"color": "#40536e"}},
        xaxis={"title": "Postings", "gridcolor": "#e9edf4", "tickformat": ","},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=12, t=12, b=12),
        height=max(290, min(440, len(items) * 32 + 80)),
        font={"family": "Inter, Segoe UI, sans-serif", "color": "#44566e"},
        showlegend=False,
    )
    st.plotly_chart(figure, width="stretch", key=title)


def sources_panel(response):
    by_id = {e["source_id"]: e for e in response.get("evidence", [])}
    for source in response.get("sources", []):
        label = f"{source['job_title']} · {source.get('company') or 'Company not listed'}"
        with st.expander(label):
            place = " · ".join(str(source[k]) for k in ("city", "country") if source.get(k))
            st.caption(place or "Location not listed")
            evidence = by_id.get(source["source_id"], {})
            st.markdown(f"**Relevant excerpt** · {source['source_id']}")
            st.write(source.get("excerpt") or evidence.get("chunk_text", "")[:320])
            url = source.get("source_url") or ""
            if url.startswith(("https://", "http://")):
                st.link_button("Original posting", url)


def render_answer(response):
    route = response["route"]
    label = "ANALYTICS" if route == "analytics" else "RAG"
    cls = "dj-route" if route == "analytics" else "dj-route dj-route-rag"
    st.markdown(f'<span class="{cls}">{label}</span>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dj-note">'
        + (
            "Calculated from the structured job database."
            if route == "analytics"
            else "Synthesized from retrieved job-posting evidence."
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(response["answer"])
    if route == "analytics" and response.get("data"):
        data = response["data"]
        if data.get("items"):
            st.dataframe(pd.DataFrame(data["items"]), hide_index=True, width="stretch")
        elif data.get("groups"):
            st.dataframe(pd.DataFrame(data["groups"]), hide_index=True)
    if route == "rag":
        meta = response["metadata"]
        st.caption(
            f"Based on {meta.get('retrieved_jobs', 0)} retrieved job postings · "
            f"{meta.get('evidence_quality', 'Evidence quality unavailable')}"
        )
        if meta.get("warning"):
            st.warning(meta["warning"])
        if response.get("skills"):
            st.caption("Skills in cited evidence · counts refer only to selected postings")
            chips([s["name"] for s in response["skills"][:10]])
        if response.get("sources"):
            section(
                "Evidence", "Open a posting to inspect the supporting excerpt and original source."
            )
        sources_panel(response)
        if meta.get("debug"):
            with st.expander("Technical retrieval details"):
                st.json(meta["debug"])
