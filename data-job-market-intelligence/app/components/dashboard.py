"""Release evidence and live index status, clearly separated in the UI."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import streamlit as st

from app.components.design import badge, empty_state, kpi, safe, source_chips
from app.components.icons import icon
from app.components.ui import ROOT, api_url, assistant_preview

PREVIEW_QUESTION = "What responsibilities are expected from Senior Data Engineers?"


def date_label(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y")
    except (ValueError, AttributeError, TypeError):
        return "Date unavailable"


@st.cache_data(ttl=60, show_spinner=False)
def validation_results():
    """Preserve the original dated release and its 20-criterion assessment."""
    snapshot = json.loads(
        (Path(__file__).parents[1] / "assets/validation_snapshot.json").read_text(encoding="utf-8")
    )
    release = ROOT / "evaluation/results/final-v2-release.json"
    if release.exists():
        try:
            data = json.loads(release.read_text(encoding="utf-8"))
            if data.get("final_commit") == snapshot["source_commit"]:
                snapshot.update(
                    tests_passed=data["tests_passed"],
                    postgresql_tests_passed=data["postgresql_tests_passed"],
                    recorded_at=data["recorded_at"],
                    source="Local final V2 validation artifact",
                )
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return snapshot


@st.cache_data(ttl=60, show_spinner=False)
def current_validation_results():
    """Recorded evidence, including explicit provenance for user Docker tests."""
    return json.loads(
        (Path(__file__).parents[1] / "assets/current_validation.json").read_text(encoding="utf-8")
    )


def home_metrics(overview, index):
    validation = current_validation_results()
    date = date_label(validation["recorded_at"])
    count = overview.get("total_jobs") if overview else None
    vectors = index.get("embeddings") if index and index.get("index_version") == "v2" else None
    with st.container(key="home_kpis"):
        cols = st.columns(4, gap="medium")
        with cols[0]:
            kpi(
                "Historical Job Postings",
                f"{count:,}" if count is not None else "Unavailable",
                "Matching postings in the historical dataset.",
                name="file",
            )
        with cols[1]:
            kpi(
                "V2 Embeddings",
                f"{vectors:,}" if vectors is not None else "Unavailable",
                "Semantic vectors stored in PostgreSQL.",
                name="database",
                accent="purple",
            )
        with cols[2]:
            kpi(
                "Tests Passed",
                validation["tests_passed"],
                f"Recorded test run · {date}",
                name="check",
                accent="green",
                href="/Validation",
            )
        with cols[3]:
            kpi(
                "Docker Runtime",
                "User verified",
                f"External Supabase · reported {date_label(validation['docker']['reported_at'])}",
                name="shield",
                accent="orange",
                href="/Validation",
            )


def index_status(index):
    ready = bool(index and index.get("ready"))
    version = (index or {}).get("index_version")
    state = "Active" if ready and version == "v2" else "V1 active" if ready else "Unavailable"
    st.html(
        '<div class="dj-index-heading"><span class="dj-caption">Live system check</span>'
        + badge(state, "success" if ready else "warning")
        + "</div>"
    )
    if not index:
        empty_state("Index status unavailable", "The API could not be reached. Try again shortly.")
        return
    values = [
        ("Index Version", (index.get("index_version") or "Unavailable").upper()),
        ("Total Embeddings", f"{index['embeddings']:,}"),
        ("Embedding Dimensions", index.get("dimensions") or "Unavailable"),
        ("Database", index.get("database") or "Unavailable"),
        ("Index State", "Ready" if ready else "Partial" if index.get("partial") else "Not ready"),
    ]
    st.html(
        "".join(
            f'<div class="dj-index-row"><span>{safe(label)}</span>'
            f"<strong>{safe(value)}</strong></div>"
            for label, value in values
        )
        + '<div class="dj-caption" style="margin-top:12px;color:#5c9cf4">'
        + icon("database", 24)
        + " &nbsp;Source-linked semantic search</div>"
    )


def preview_card(filters, index):
    st.html(f'<div class="dj-preview-q">{safe(PREVIEW_QUESTION)}</div>')
    if not index or not index.get("ready"):
        st.caption("Connect the data service to load a grounded example.")
        st.page_link("pages/3_AI_Assistant.py", label="Open AI Assistant →")
        return
    try:
        with st.spinner("Retrieving a grounded example…"):
            result = assistant_preview(
                api_url(),
                tuple(sorted(filters.items())),
                index.get("created_at"),
            )
    except (httpx.HTTPError, ValueError):
        st.warning("The example could not be loaded. You can retry in AI Assistant.")
        st.page_link("pages/3_AI_Assistant.py", label="Open AI Assistant →")
        return
    # This is a displayed excerpt of the actual answer, not a new generated claim.
    answer = result.get("answer", "")
    excerpt = answer[:330].rsplit(" ", 1)[0] + "…" if len(answer) > 330 else answer
    route = result.get("route", "")
    metadata = result.get("metadata", {})
    quality = metadata.get("evidence_quality", "Evidence unavailable")
    count = metadata.get("retrieved_jobs", len(result.get("sources", [])))
    cls = "dj-route" + (" dj-route-rag" if route == "rag" else "")
    st.html(
        f'<div class="dj-preview-answer"><span class="{cls}">{safe(route.upper())}</span>'
        f"<p>{safe(excerpt).replace(chr(10), '<br>')}</p></div>"
        '<div class="dj-preview-footer">'
        + badge(quality, "success" if quality.startswith("Strong") else "warning")
        + source_chips(result.get("sources", []))
        + "</div>"
        f'<div class="dj-caption">{count} retrieved postings · excerpt of the actual answer</div>'
    )
    if st.button("Open AI Assistant →", key="open_preview", width="stretch"):
        st.session_state.setdefault("messages", []).extend(
            [
                {"role": "user", "content": PREVIEW_QUESTION},
                {"role": "assistant", "content": result},
            ]
        )
        st.switch_page("pages/3_AI_Assistant.py")
