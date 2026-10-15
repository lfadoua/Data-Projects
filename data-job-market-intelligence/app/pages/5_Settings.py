"""Real workspace preferences and read-only system diagnostics; no credentials."""

import streamlit as st

from app.components.dashboard import index_status
from app.components.design import panel
from app.components.preferences import preferences, save_preference
from app.components.ui import (
    assistant_preview,
    cached_get,
    cached_health,
    get_facets,
    read,
    setup,
)

setup("Settings", "Make the workspace yours and inspect its connection status.")
prefs = preferences()
for name, value in prefs.items():
    st.session_state.setdefault(f"pref_{name}", value)
left, right = st.columns([1.1, 1], gap="medium")
with left:
    with panel("Workspace Preferences", "settings_preferences"):
        st.selectbox(
            "Jobs per page",
            [6, 12, 24],
            key="pref_jobs_page_size",
            on_change=save_preference,
            args=("jobs_page_size",),
            help="Controls pagination in Job Explorer.",
        )
        st.toggle(
            "Compact job cards",
            key="pref_compact_jobs",
            on_change=save_preference,
            args=("compact_jobs",),
            help="Show a shorter description preview in Job Explorer.",
        )
        st.toggle(
            "Show technical retrieval details",
            key="pref_show_technical",
            on_change=save_preference,
            args=("show_technical",),
            help="Shows returned debug metadata when the backend provides it.",
        )
        st.caption(
            "These preferences apply to this browser session. "
            "No account or subscription is required."
        )
    with panel("Historical Dataset", "settings_dataset"):
        st.write("Collected January 12–17, 2024.")
        st.caption(
            "Original publication dates are unavailable. The dashboard does not infer "
            "recent hiring trends or current job availability."
        )
        st.page_link("pages/4_Validation.py", label="Review validation and limitations →")
with right:
    with panel("System Status", "settings_status"):
        index_status(read("/api/system/status", quiet=True))
        if st.button("Refresh system and cached data", width="stretch", icon=":material/refresh:"):
            cached_get.clear()
            cached_health.clear()
            get_facets.clear()
            assistant_preview.clear()
            st.rerun()
        st.caption("Refresh clears UI caches only. It does not reload data or rebuild the index.")
