"""Dated release validation, deliberately separate from live backend readiness."""

import pandas as pd
import streamlit as st

from app.components.dashboard import date_label, index_status, validation_results
from app.components.design import kpi, panel
from app.components.ui import read, setup

setup("Validation", "Measured project readiness, transparent evidence and remaining limitations.")
release = validation_results()
date = date_label(release["recorded_at"])
st.info(f"Historical release verification · {date}. These test results are not a new test run.")
columns = st.columns(4, gap="medium")
with columns[0]:
    kpi("Tests Passed", release["tests_passed"], f"Verified {date}", name="check", accent="green")
with columns[1]:
    kpi(
        "PostgreSQL Tests",
        release["postgresql_tests_passed"],
        "Real database integration checks",
        name="database",
        accent="purple",
    )
with columns[2]:
    kpi(
        "Vectors Verified",
        f"{release['vectors_verified']:,}",
        "Compared with every saved batch",
        name="shield",
    )
with columns[3]:
    validated, total = release["criteria_validated"], release["criteria_total"]
    kpi(
        "Validation Criteria",
        f"{validated} / {total}",
        "Docker runtime validation remains partial",
        name="shield",
        accent="orange",
        progress=100 * validated / total,
    )

left, right = st.columns([1.8, 1], gap="medium")
with left:
    with panel(
        "Definition of Done", "validation_criteria", f"All 20 original criteria · verified {date}"
    ):
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
        st.warning("Docker runtime: not fully validated.")
        st.write(
            "Compose passed its official schema and 16 static checks. "
            "Container builds and startup were not executed on this machine."
        )
        st.info("Hosted GitHub Actions execution has not been confirmed.")
        st.caption(
            "Optional OpenAI/Ollama generation was not included in the local release validation."
        )
    with panel("Verification Provenance", "validation_provenance"):
        st.caption(release["source"])
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
