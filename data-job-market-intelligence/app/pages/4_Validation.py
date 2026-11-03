"""Dated release validation, deliberately separate from live backend readiness."""

import pandas as pd
import streamlit as st

from app.components.dashboard import (
    current_validation_results,
    date_label,
    index_status,
    validation_results,
)
from app.components.design import kpi, panel
from app.components.ui import read, setup

setup("Validation", "Measured project readiness, transparent evidence and remaining limitations.")
release = validation_results()
current = current_validation_results()
date = date_label(current["recorded_at"])
historical_date = date_label(release["recorded_at"])
st.info(f"Recorded test run · {date}. Opening this page does not execute tests.")
st.caption(
    f"Recent evidence: {current['test_scope']}. "
    f"Original release: {historical_date}, {release['tests_passed']} tests and "
    f"{release['criteria_validated']}/20 criteria. These are separate assessments."
)
with st.container(key="validation_kpis"):
    columns = st.columns(4, gap="medium")
with columns[0]:
    kpi("Tests Passed", current["tests_passed"], f"Recorded {date}", name="check", accent="green")
with columns[1]:
    kpi(
        "PostgreSQL Tests",
        current["postgresql_tests_passed"],
        "Real database integration checks",
        name="database",
        accent="purple",
    )
with columns[2]:
    kpi(
        "Vectors Verified",
        f"{release['vectors_verified']:,}",
        f"Full checkpoint comparison · {historical_date}",
        name="shield",
    )
with columns[3]:
    kpi(
        "Docker Runtime",
        "User verified",
        f"Reported {date_label(current['docker']['reported_at'])}",
        name="shield",
        accent="orange",
    )

left, right = st.columns([1.8, 1], gap="medium")
with left:
    with panel(
        "Historical Definition of Done",
        "validation_criteria",
        f"Original release · {historical_date} · {release['criteria_validated']}/20 at that time",
    ):
        st.caption(
            "This is the original assessment, preserved unchanged. Later Docker tests "
            "cover the external-Supabase setup and do not retroactively change this score."
        )
        frame = pd.DataFrame(release["criteria"])
        frame["status"] = frame["status"].map(
            {
                "validated": "✓ Implemented and validated",
                "partial": "△ Implemented but not fully validated",
            }
        )
        st.dataframe(
            frame.rename(columns={"number": "#", "criterion": "Criterion", "status": "Status"}),
            hide_index=True,
            width="stretch",
            height=650,
        )
with right:
    with panel(
        "Live Index Status", "validation_live", "Current API state, independent of past tests"
    ):
        index_status(read("/api/system/status", quiet=True))
    with panel("Known Validation Limits", "validation_limits"):
        st.info("Docker runtime: user-verified locally with external Supabase.")
        st.write(
            "The user reported healthy API/frontend containers, SQL analytics and "
            "extractive RAG on ports 8002/8502. Compose configuration was checked "
            "independently; the Docker engine was not reachable during that check."
        )
        st.info("Hosted GitHub Actions execution has not been confirmed.")
        st.caption(
            "Local Qwen 1.5B generation was tested separately on 30 October. "
            "Four of four measured attempts returned accepted bounded responses; "
            "two responses had a rejected claim. Generative Docker execution is unverified."
        )
    with panel("Verification Provenance", "validation_provenance"):
        st.write(f"**Test method:** {current['test_provenance']}")
        st.write(f"**Docker method:** {current['docker']['provenance']}")
        st.caption(current["source"])
        st.caption("Historical release commit (not the current uncommitted changes):")
        st.code(release["source_commit"], language=None)
        st.caption(
            "Citation traceability, six API routes and ten real questions "
            "are documented in the final project report."
        )
        st.download_button(
            "Download validation snapshot",
            data=pd.DataFrame(release["criteria"]).to_csv(index=False),
            file_name="datajob-validation-criteria.csv",
            mime="text/csv",
            width="stretch",
        )
