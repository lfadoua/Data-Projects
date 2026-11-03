"""Shared light-theme presentation components for the Streamlit workspace."""

from contextlib import contextmanager
from html import escape
from pathlib import Path

import streamlit as st

from app.components.icons import LOGO, MOUNTAIN, icon, svg_image

NAVIGATION = [
    ("Home", "Home.py", "home"),
    ("Market Overview", "pages/1_Market_Overview.py", "bar_chart"),
    ("Job Explorer", "pages/2_Job_Explorer.py", "search"),
    ("AI Assistant", "pages/3_AI_Assistant.py", "auto_awesome"),
    ("Validation", "pages/4_Validation.py", "verified_user"),
    ("Settings", "pages/5_Settings.py", "settings"),
]


def safe(value):
    return escape(str(value if value is not None else ""), quote=True)


def theme_css():
    return (Path(__file__).parents[1] / "assets/theme.css").read_text(encoding="utf-8")


def shell(title, active, health):
    st.set_page_config(
        page_title=f"{title} | DataJob",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.html(f"<style>{theme_css()}</style>")
    with st.sidebar:
        st.html(
            f'<div class="dj-brand">{LOGO}<div><strong>DataJob</strong>'
            "<small>Market Intelligence</small></div></div>"
        )
        for index, (label, path, material) in enumerate(NAVIGATION):
            with st.container(key=f"nav_{index}"):
                if label == active:
                    st.html('<span class="dj-nav-active"></span>')
                st.page_link(path, label=label, icon=f":material/{material}:", width="stretch")
        with st.container(key="sidebar_bottom"):
            with st.container(key="promo_card"):
                st.html(
                    '<div class="dj-promo">' + "<h3>Explore historical job data</h3>"
                    "<p>Skills and responsibilities recorded in January 2024.</p></div>"
                )
                st.page_link(
                    "pages/2_Job_Explorer.py", label="Browse historical postings →", width="stretch"
                )
            st.html(
                '<div class="dj-workspace"><span class="dj-workspace-icon">'
                + icon("workspace", 18)
                + "</span><div><strong>Local workspace</strong>"
                "<small>Historical data · Jan 2024</small></div></div>"
            )
            if not health:
                st.caption("Backend unavailable · retry from Settings")


def hero(title, subtitle, home=False):
    if not home:
        st.html(
            '<div class="dj-page-head"><div class="dj-eyebrow">Data intelligence workspace</div>'
            f"<h1>{safe(title)}</h1><p>{safe(subtitle)}</p></div>"
        )
        return
    features = [
        ("database", "Real job market data"),
        ("search", "Semantic search with V2 embeddings"),
        ("shield", "Grounded AI answers with citations"),
    ]
    badges = "".join(
        f'<span class="dj-feature">{icon(name, 16)}{safe(label)}</span>' for name, label in features
    )
    st.html(
        '<div class="dj-hero"><div class="dj-hero-art">' + MOUNTAIN + "</div>"
        "<h1>Data Job Market <span>Intelligence</span></h1>"
        f"<p>{safe(subtitle)}</p>"
        f'<div class="dj-feature-row">{badges}</div>'
        '<div class="dj-hero-quote"><strong>From job data<br>to career clarity.</strong></div></div>'
    )


def kpi(label, value, foot="", name="chart", accent="", progress=None, href=None):
    ring = ""
    cls = "dj-kpi"
    if progress is not None:
        percent = max(0, min(100, progress))
        offset = 175.93 * (1 - percent / 100)
        cls += " has-ring"
        ring = (
            f'<svg class="dj-kpi-ring" viewBox="0 0 70 70" role="img" '
            f'aria-label="{percent:.0f} percent validated">'
            '<circle cx="35" cy="35" r="28" fill="none" stroke="#edf3fb" stroke-width="6"/>'
            f'<circle cx="35" cy="35" r="28" fill="none" stroke="#1896f5" stroke-width="6" '
            f'stroke-dasharray="175.93" stroke-dashoffset="{offset:.2f}" '
            'stroke-linecap="round" transform="rotate(-90 35 35)"/>'
            '<text x="35" y="40" text-anchor="middle" font-family="Arial,sans-serif" '
            f'font-size="12" font-weight="700" fill="#111827">{percent:.0f}%</text></svg>'
        )
        ring = svg_image(ring, "dj-kpi-ring", f"{percent:.0f}% validated")
    color = {"purple": "#8b5cf6", "green": "#0cab8a", "orange": "#fb923c"}.get(accent, "#1a8bfa")
    content = (
        f'<div class="dj-kpi-top"><span class="dj-kpi-icon {safe(accent)}">'
        + icon(name, 25, color)
        + f'</span><div><div class="dj-kpi-label">{safe(label)}</div>'
        f'<div class="dj-kpi-value">{safe(value)}</div></div></div>'
        f'<div class="dj-kpi-foot">{safe(foot)}</div>{ring}'
    )
    if href:
        path = next(path for _, path, _ in NAVIGATION if f"/{_label(path)}" == href)
        with st.container(key=f"kpi_link_{name}"):
            st.html(f'<div class="{cls}">{content}</div>')
            st.page_link(path, label=f"View {label}", width="stretch")
    else:
        st.html(f'<div class="{cls}">{content}</div>')


def badge(text, tone="success", name="check"):
    modifier = "" if tone == "success" else f" {tone}"
    color = {"neutral": "#65789a", "warning": "#976014"}.get(tone, "#04856b")
    return f'<span class="dj-badge{modifier}">{icon(name, 12, color)}{safe(text)}</span>'


def _label(path):
    return path.rsplit("/", 1)[-1].split("_", 1)[-1].removesuffix(".py")


@contextmanager
def panel(title, key, subtitle="", action=None):
    with st.container(key=f"card_{key}"):
        note = f"<small>{safe(subtitle)}</small>" if subtitle else ""
        if title or subtitle or action:
            if action:
                heading, link = st.columns([3, 1], gap="small")
            else:
                heading = st.container()
            with heading:
                st.html(
                    f'<div class="dj-card-header"><div><h2>{safe(title)}</h2>{note}</div></div>'
                )
            if action:
                label, href = action
                path = next(path for _, path, _ in NAVIGATION if f"/{_label(path)}" == href)
                with link:
                    st.page_link(path, label=label, width="stretch")
        yield


def section(title, subtitle=""):
    st.html(f'<div class="dj-section"><h2>{safe(title)}</h2><p>{safe(subtitle)}</p></div>')


def chips(values, neutral=False):
    cls = "dj-chip dj-chip-neutral" if neutral else "dj-chip"
    st.html("".join(f'<span class="{cls}">{safe(value)}</span>' for value in values))


def empty_state(title, description):
    st.html(
        f'<div class="dj-empty">{icon("search", 29)}'
        f"<h3>{safe(title)}</h3><p>{safe(description)}</p></div>"
    )


def source_chips(sources):
    links = []
    for source in sources:
        source_id = safe(source.get("source_id", ""))
        url = source.get("source_url") or ""
        if url.startswith(("https://", "http://")):
            links.append(
                f'<a class="dj-source-chip" href="{safe(url)}" target="_blank" '
                f'rel="noopener noreferrer" title="{safe(source.get("job_title"))}">'
                f"[{source_id}]</a>"
            )
        else:
            links.append(f'<span class="dj-source-chip">[{source_id}]</span>')
    return "".join(links)
