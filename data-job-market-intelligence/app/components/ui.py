"""HTTP-only UI state, navigation, filtering and evidence components."""

import os
import re
from math import isfinite
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from dotenv import dotenv_values

from app.components.design import (
    badge,
    chips,
    empty_state,
    hero,
    section,
    shell,
    source_chips,
)
from app.components.icons import icon
from app.components.preferences import preferences

ROOT = Path(__file__).resolve().parents[2]
FILTER_FIELDS = [
    ("job_title", "Job title"),
    ("city", "City"),
    ("seniority", "Seniority"),
    ("workplace_type", "Workplace type"),
    ("company", "Company"),
    ("skill", "Skills"),
]
RESPONSE_MODES = {
    None: "Configured default",
    "extractive": "Extractive fast",
    "generative": "Generative Ollama",
}


def _save_response_mode():
    value = st.session_state["_assistant_response_mode"]
    st.session_state["assistant_response_mode"] = None if value == "configured" else value


def response_mode_selector():
    mode = st.session_state.setdefault("assistant_response_mode", "extractive")
    if mode not in RESPONSE_MODES:
        mode = st.session_state["assistant_response_mode"] = "extractive"
    # Keep the preference after Streamlit cleans up widgets on other pages.
    st.session_state["_assistant_response_mode"] = mode or "configured"
    st.selectbox(
        "Response mode",
        ["configured", "extractive", "generative"],
        format_func=lambda value: RESPONSE_MODES[None if value == "configured" else value],
        key="_assistant_response_mode",
        on_change=_save_response_mode,
        help=(
            "Applies to descriptive questions; counts always use SQL. "
            "Configured default keeps the server's existing behavior. "
            "Extractive fast is recommended for this PC and selects exact quotes "
            "without calling the LLM."
        ),
    )
    return st.session_state["assistant_response_mode"]


def assistant_body(question, filters, response_mode=None):
    if response_mode not in RESPONSE_MODES:
        raise ValueError("Unknown response mode")
    body = {"question": question, "filters": dict(filters)}
    if response_mode is not None:
        body["response_mode"] = response_mode
    return body


def assistant_wait_message(response_mode):
    return {
        "extractive": "Retrieving relevant postings and selecting exact quotes…",
        "generative": "Retrieving postings, generating a synthesis and checking its sources…",
    }.get(response_mode, "Searching relevant postings and checking the evidence…")


def answer_caption(metadata):
    """Describe the returned output, including old responses without new metadata."""
    mode = metadata.get("mode")
    output = metadata.get("output_mode")
    attempted = metadata.get("generation_attempted")
    parts = []
    if metadata.get("insufficient_evidence") or output == "insufficient_evidence":
        parts.append("Insufficient evidence")
    if mode == "extractive_fallback":
        parts.append("Extractive fallback")
    elif mode == "extractive":
        parts.append("Extractive")
    elif attempted is False:
        parts.append("No LLM call")
    elif mode in {"ollama", "openai"}:
        parts.append("Ollama" if mode == "ollama" else "OpenAI")
    elif attempted is True:
        parts.append("Generation attempted")
    if output in {"extractive_quotes", "llm_selected_quotes"}:
        parts.append("Exact quotes")
    elif output == "generated_synthesis":
        parts.append("Natural synthesis")
    elif output == "extractive_synthesis":
        parts.append("Local synthesis")
    timings = metadata.get("timings_ms")
    milliseconds = timings.get("total") if isinstance(timings, dict) else None
    seconds = None
    for value, scale in ((milliseconds, 1000), (metadata.get("latency_seconds"), 1)):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isfinite(value) and value >= 0:
                seconds = value / scale
                break
    if seconds is not None:
        parts.append(f"{seconds:.2f} s" if seconds < 1 else f"{seconds:.1f} s")
    return " · ".join(parts)


def api_url():
    values = dotenv_values(ROOT / ".env", interpolate=False)
    return (
        os.getenv("STREAMLIT_API_URL") or values.get("STREAMLIT_API_URL") or "http://127.0.0.1:8000"
    ).rstrip("/")


def request(path, params=None, body=None, quiet=False):
    try:
        with httpx.Client(timeout=150 if body is not None else 30) as client:
            response = (
                client.post(api_url() + path, json=body)
                if body is not None
                else client.get(api_url() + path, params=params)
            )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        if not quiet:
            if exc.response.status_code == 422:
                st.warning(
                    "Check the question, search length and selected filters, then try again."
                )
            else:
                st.error("The service is temporarily unavailable. Please try again in a moment.")
        return None
    except (httpx.HTTPError, ValueError):
        if not quiet:
            st.error(
                "We couldn't reach the service. Check the system status in Settings and retry."
            )
        return None


@st.cache_data(ttl=45, show_spinner=False)
def cached_get(url, path, items=()):
    response = httpx.get(url + path, params=dict(items), timeout=45)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=15, show_spinner=False)
def cached_health(url):
    response = httpx.get(url + "/health", timeout=20)
    response.raise_for_status()
    return response.json()


def read(path, params=None, quiet=False):
    try:
        if path == "/health":
            return cached_health(api_url())
        return cached_get(api_url(), path, tuple(sorted((params or {}).items())))
    except (httpx.HTTPError, ValueError):
        if not quiet:
            empty_state(
                "Data is temporarily unavailable",
                "The service may be reconnecting. Retry shortly "
                "or check the system status in Settings.",
            )
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_facets(url):
    response = httpx.get(url + "/api/analytics/filters", timeout=40)
    response.raise_for_status()
    return response.json()


def facets_or_empty():
    try:
        return get_facets(api_url())
    except (httpx.HTTPError, ValueError):
        return {}


def active_filters():
    return dict(st.session_state.setdefault("market_filters", {}))


def _save_country():
    filters = st.session_state.setdefault("market_filters", {})
    value = st.session_state.get("top_country", "All countries")
    if value == "All countries":
        filters.pop("country", None)
    else:
        filters["country"] = value
    st.session_state["jobs_page"] = 1


def _save_filter(field):
    filters = st.session_state.setdefault("market_filters", {})
    value = st.session_state.get("filter_" + field, "All")
    if value == "All":
        filters.pop(field, None)
    else:
        filters[field] = value
    st.session_state["jobs_page"] = 1


def reset_filters():
    st.session_state["market_filters"] = {}
    st.session_state["jobs_page"] = 1
    for key in list(st.session_state):
        if key.startswith("filter_") or key == "top_country":
            del st.session_state[key]


def _route_search(value):
    value = value.strip()
    if not value:
        return
    question = value.endswith("?") or re.match(
        r"^(what|how|which|why|describe|explain|tell me|show me)\b", value, re.I
    )
    if question:
        st.session_state["pending_question"] = value
        st.switch_page("pages/3_AI_Assistant.py")
    else:
        st.session_state["jobs_search"] = value
        st.session_state["jobs_page"] = 1
        st.switch_page("pages/2_Job_Explorer.py")


def top_header(health):
    facets = facets_or_empty()
    with st.container(key="top_header"):
        search, country, historical, status = st.columns(
            [5.4, 1.65, 1.55, 1.0], gap="small", vertical_alignment="center"
        )
        with search:
            with st.form("workspace_search", border=False):
                field, action = st.columns([10, 1], gap="small", vertical_alignment="center")
                with field:
                    value = st.text_input(
                        "Search jobs, skills, companies or ask AI",
                        placeholder="Search jobs, skills, companies or ask AI...",
                        label_visibility="collapsed",
                        max_chars=200,
                        key="workspace_search_input",
                        icon=":material/search:",
                    )
                with action:
                    submitted = st.form_submit_button("→", help="Search jobs or send a question")
            if submitted:
                _route_search(value)
        with country:
            options = ["All countries"] + facets.get("country", [])
            selected = active_filters().get("country", "All countries")
            if selected not in options:
                options.append(selected)
            st.selectbox(
                "Country",
                options,
                index=options.index(selected),
                key="top_country",
                label_visibility="collapsed",
                on_change=_save_country,
            )
        with historical:
            st.html(
                '<div class="dj-historical" title="Collected January 12–17, 2024; '
                'publication dates unavailable">'
                + icon("calendar", 15)
                + "<span>Historical dataset</span></div>"
            )
        with status:
            online = bool(health and health.get("database") == "connected")
            cls = "dj-top-status" + ("" if online else " offline")
            text = "Connected" if online else "Unavailable"
            st.html(
                f'<div class="{cls}" role="status" title="API health checked on page load; '
                f'cached for up to 15 seconds"><span class="dj-dot"></span>{text}</div>'
            )


def setup(title, subtitle="", active=None, home=False):
    health = read("/health", quiet=True)
    shell(title, active or title, health)
    top_header(health)
    hero(title, subtitle, home=home)
    return health


def filters_panel(expanded=False):
    facets = facets_or_empty()
    if not facets:
        st.warning("Filters will be available when the data service reconnects.")
        return active_filters()
    with st.expander("Refine filters", expanded=expanded, icon=":material/tune:"):
        for row in (FILTER_FIELDS[:3], FILTER_FIELDS[3:]):
            for column, (field, label) in zip(st.columns(3), row, strict=True):
                with column:
                    options = ["All"] + facets.get(field, [])
                    value = active_filters().get(field, "All")
                    if value not in options:
                        options.append(value)
                    st.selectbox(
                        label,
                        options,
                        index=options.index(value),
                        key="filter_" + field,
                        on_change=_save_filter,
                        args=(field,),
                    )
        st.button("Reset filters", on_click=reset_filters, icon=":material/filter_alt_off:")
    values = active_filters()
    if values:
        chips(
            [f"{key.replace('_', ' ').title()}: {value}" for key, value in values.items()],
            neutral=True,
        )
    return values


def sources_panel(response, expanded_first=False):
    by_id = {e["source_id"]: e for e in response.get("evidence", [])}
    sources = response.get("sources", [])
    if not sources:
        empty_state("No cited sources", "This answer has no cited job-posting evidence to inspect.")
        return
    for index, source in enumerate(sources):
        label = f"{source['source_id']} · {source['job_title']}"
        with st.expander(label, expanded=expanded_first and index == 0):
            st.caption(source.get("company") or "Company not listed")
            place = " · ".join(str(source[k]) for k in ("city", "country") if source.get(k))
            st.caption(place or "Location not listed")
            evidence = by_id.get(source["source_id"], {})
            passage = (
                evidence.get("chunk_text")
                or source.get("excerpt")
                or "No source passage was supplied with this answer."
            )
            if len(passage) > 900:
                st.caption("Scroll within the passage to read the full retrieved text.")
            with st.container(height=320 if len(passage) > 900 else "content", border=False):
                st.write(passage)
            url = source.get("source_url") or ""
            if url.startswith(("https://", "http://")):
                st.link_button("Original posting ↗", url, width="stretch")


def render_answer(response, key="answer", show_sources=True):
    route = response["route"]
    meta = response.get("metadata") or {}
    cls = "dj-route" + (" dj-route-rag" if route == "rag" else "")
    explanation = (
        "Calculated from the structured job database."
        if route == "analytics"
        else "Based on selected historical job postings."
    )
    label = "SQL ANALYTICS" if route == "analytics" else "RAG"
    st.html(f'<span class="{cls}">{label}</span><div class="dj-note">{explanation}</div>')
    caption = answer_caption(meta)
    if caption:
        st.caption(caption)
    if meta.get("insufficient_evidence") or meta.get("output_mode") == "insufficient_evidence":
        st.warning(
            "There is not enough matching evidence for a supported answer. "
            "Try a broader question or remove a filter."
        )
    # Preserve every word and citation; make typographic bullet lines readable Markdown.
    st.markdown(response["answer"].replace("\n• ", "\n\n- "))
    filters = meta.get("filters") or {}
    if filters:
        chips([f"{k.replace('_', ' ')}: {v}" for k, v in filters.items()], neutral=True)
    if route == "analytics" and response.get("data"):
        data = response["data"]
        items = data.get("items") or data.get("groups")
        if items:
            with st.expander("Calculated statistics"):
                st.dataframe(
                    pd.DataFrame(items), hide_index=True, width="stretch", key=f"{key}_table"
                )
    if route == "rag":
        quality = meta.get("evidence_quality", "Evidence quality unavailable")
        tone = "success" if quality.startswith("Strong") else "warning"
        count = meta.get("retrieved_jobs", len(response.get("sources", [])))
        st.html(
            f'<div class="dj-preview-footer">{badge(quality, tone)}'
            f'<span class="dj-caption">{count} retrieved job postings</span>'
            + source_chips(response.get("sources", []))
            + "</div>"
        )
        if meta.get("mode") == "extractive_fallback":
            st.warning(
                "Generation was unavailable or failed source checks. "
                "Showing an extractive fallback."
            )
        elif meta.get("warning"):
            st.warning(meta["warning"])
        grounding = meta.get("grounding")
        if isinstance(grounding, dict):
            if grounding.get("rejected_claims", 0):
                st.caption("Some claims were removed by source checks; paraphrases need review.")
            elif (
                grounding.get("strategy") == "conservative_paraphrase"
                and grounding.get("source_ids_validated") is True
                and grounding.get("exact_quotes_validated") is True
            ):
                st.caption("Source checks passed; semantic support is not independently verified.")
        if response.get("skills"):
            st.caption("Skills in selected evidence · not market-wide frequencies")
            chips([s["name"] for s in response["skills"][:10]])
        if show_sources:
            section("Source evidence", "Inspect the supporting text and original posting.")
            sources_panel(response)
        technical = {
            name: meta[name]
            for name in (
                "mode",
                "requested_mode",
                "output_mode",
                "generation_attempted",
                "generation_used",
                "fallback_reason",
                "timings_ms",
                "grounding",
                "warning",
                "debug",
            )
            if name in meta
        }
        if technical and preferences()["show_technical"]:
            with st.expander("Technical retrieval details"):
                st.json(technical)


@st.cache_data(ttl=600, show_spinner=False)
def assistant_preview(url, filters, index_identity, response_mode="extractive"):
    response = httpx.post(
        url + "/api/assistant/query",
        json=assistant_body(
            "What responsibilities are expected from Senior Data Engineers?", filters, response_mode
        ),
        timeout=150,
    )
    response.raise_for_status()
    return response.json()
