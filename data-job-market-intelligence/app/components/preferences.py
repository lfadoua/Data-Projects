"""Session preferences kept separately from Streamlit's temporary widget keys."""

import streamlit as st

DEFAULTS = {"jobs_page_size": 12, "compact_jobs": True, "show_technical": False}


def preferences():
    return st.session_state.setdefault("workspace_preferences", DEFAULTS.copy())


def save_preference(name):
    preferences()[name] = st.session_state[f"pref_{name}"]
    if name == "jobs_page_size":
        st.session_state["jobs_page"] = 1
