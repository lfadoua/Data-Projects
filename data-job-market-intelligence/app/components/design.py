"""Streamlit design system: stable components and a small, scoped CSS layer."""

from html import escape

import streamlit as st

CSS = """
<style>
:root { --ink:#15243b; --muted:#64748b; --line:#e3e9f1; --blue:#285cdb; --teal:#0f9e94; }
.stApp { background:#f5f7fb; color:var(--ink); }
[data-testid="stSidebar"] { background:#101d32; }
[data-testid="stSidebarNav"] { display:none; }
[data-testid="stSidebar"] * { color:#e6edf8; }
[data-testid="stSidebar"] .stSelectbox label { color:#b8c6da!important; }
[data-testid="stSidebar"] [data-baseweb="select"] * { color:#213047!important; }
[data-testid="stSidebar"] [role="combobox"],
[data-testid="stSidebar"] [role="combobox"] *,
[data-testid="stSidebar"] input {
  color:#24344a!important; -webkit-text-fill-color:#24344a!important;
}
.block-container { max-width:1420px; padding-top:1.7rem; padding-bottom:4rem; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.035em; }
h1 { font-weight:760!important; }
.dj-brand { padding:1.1rem .2rem 1.2rem; border-bottom:1px solid #33445b; margin-bottom:1rem; }
.dj-brand-mark { display:inline-block; background:linear-gradient(135deg,#3885ff,#13b3a1); border-radius:12px; padding:.43rem .65rem; font-weight:800; margin-right:.55rem; }
.dj-brand strong { font-size:1.04rem; letter-spacing:-.02em; }
.dj-brand p { color:#aebdd1!important; font-size:.81rem; margin:.6rem 0 0; line-height:1.4; }
.dj-status { background:#1b304a; padding:.7rem .8rem; border:1px solid #314c69; border-radius:12px; color:#dceafb; font-size:.82rem; margin:1rem 0; }
.dj-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#28d5a5; margin-right:7px; }
.dj-eyebrow { color:#2e67d6; font-size:.75rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; margin-bottom:.4rem; }
.dj-hero { background:linear-gradient(116deg,#142846 0%,#1d4380 63%,#196f81 100%); color:white; border-radius:20px; padding:2.2rem 2.5rem; margin:0 0 1.5rem; box-shadow:0 18px 40px rgba(25,49,88,.13); }
.dj-hero h1 { color:white!important; font-size:2.2rem!important; margin:.15rem 0 .45rem; }
.dj-hero p { color:#dce8fa; font-size:1.04rem; margin:0; max-width:780px; }
.dj-hero .dj-eyebrow { color:#75e3d1; }
.dj-hero-note { color:#a9c2e2; font-size:.79rem; margin-top:1.15rem; }
.dj-kpi { background:white; border:1px solid var(--line); border-radius:16px; padding:1.2rem 1.3rem; min-height:170px; box-shadow:0 6px 18px rgba(35,55,85,.035); }
.dj-kpi-label { color:var(--muted); font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
.dj-kpi-value { font-size:1.5rem; line-height:1.2; font-weight:760; color:var(--ink); margin-top:.65rem; overflow-wrap:anywhere; }
.dj-kpi-foot { color:#8290a5; font-size:.76rem; margin-top:.35rem; }
.dj-section { margin:1.55rem 0 .7rem; }
.dj-section h2 { font-size:1.17rem!important; margin:0!important; }
.dj-section p { color:var(--muted); font-size:.83rem; margin:.25rem 0 0; }
.dj-chip { display:inline-block; border-radius:999px; padding:.25rem .62rem; background:#e9efff; color:#2854b5; font-size:.73rem; font-weight:650; margin:.16rem .25rem .16rem 0; }
.dj-chip-neutral { background:#edf2f7; color:#516278; }
.dj-route { display:inline-block; border-radius:7px; padding:.2rem .48rem; color:#1d5bce; background:#e9f0ff; font-size:.7rem; font-weight:800; letter-spacing:.06em; margin-right:.45rem; }
.dj-route-rag { background:#e5f7f3; color:#127e70; }
.dj-note { color:var(--muted); font-size:.79rem; margin:.35rem 0 .7rem; }
.dj-job-head { font-size:1.12rem; font-weight:760; margin:.2rem 0 .3rem; }
.dj-job-meta { color:#5f7188; font-size:.84rem; margin-bottom:.45rem; }
.dj-job-divider { border-top:1px solid #eef1f6; margin:.55rem 0; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.dj-job-head) { background:white; border:1px solid var(--line); border-radius:15px; box-shadow:0 5px 16px rgba(29,48,77,.035); }
div[data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:16px; background:white; padding:.35rem .65rem; margin:.55rem 0; }
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:#eef4ff; border-color:#dce8fb; }
div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:11px; background:white; }
.stButton button, .stLinkButton a { border-radius:9px!important; font-weight:650!important; }
[data-testid="stAlert"] { border-radius:12px; }
@media (max-width:700px) { .dj-hero { padding:1.45rem; } .dj-hero h1 { font-size:1.75rem!important; } .block-container { padding-top:1rem; } }
</style>
"""


def safe(value):
    return escape(str(value if value is not None else ""), quote=True)


def shell(title, subtitle, request):
    st.set_page_config(
        page_title=f"{title} | Data Job Market Intelligence", page_icon="◈", layout="wide"
    )
    st.markdown(CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(
            '<div class="dj-brand"><span class="dj-brand-mark">◈</span>'
            "<strong>Data Job Market Intelligence</strong>"
            "<p>Understand what employers actually ask for.</p></div>",
            unsafe_allow_html=True,
        )
        st.page_link("Home.py", label="Home", icon=":material/home:")
        st.page_link(
            "pages/1_Market_Overview.py", label="Market Overview", icon=":material/bar_chart:"
        )
        st.page_link("pages/2_Job_Explorer.py", label="Job Explorer", icon=":material/search:")
        st.page_link(
            "pages/3_AI_Assistant.py", label="AI Assistant", icon=":material/auto_awesome:"
        )
        status = request("/health", quiet=True)
        if status:
            st.markdown(
                '<div class="dj-status"><span class="dj-dot"></span>'
                + f"{status['jobs']:,} postings · "
                + ("Index ready" if status["index_ready"] else "Index unavailable")
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="dj-status">Backend unavailable</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dj-hero"><div class="dj-eyebrow">DATA INTELLIGENCE / HISTORICAL SNAPSHOT</div>'
        f"<h1>{safe(title)}</h1><p>{safe(subtitle)}</p>"
        '<div class="dj-hero-note">Job-posting evidence and structured counts · not a live market feed</div></div>',
        unsafe_allow_html=True,
    )


def kpi(label, value, foot=""):
    st.markdown(
        f'<div class="dj-kpi"><div class="dj-kpi-label">{safe(label)}</div>'
        f'<div class="dj-kpi-value">{safe(value)}</div>'
        f'<div class="dj-kpi-foot">{safe(foot)}</div></div>',
        unsafe_allow_html=True,
    )


def section(title, subtitle=""):
    st.markdown(
        f'<div class="dj-section"><h2>{safe(title)}</h2><p>{safe(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def chips(values, neutral=False):
    class_name = "dj-chip dj-chip-neutral" if neutral else "dj-chip"
    st.markdown(
        "".join(f'<span class="{class_name}">{safe(value)}</span>' for value in values),
        unsafe_allow_html=True,
    )


def empty_state(title, description):
    st.info(f"**{title}**\n\n{description}")
