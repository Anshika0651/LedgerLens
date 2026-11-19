from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from ledgerlens import database as db
from ledgerlens.components import metric, render_stepper
from ledgerlens.service import report_frame

logger = logging.getLogger(__name__)


def _mark_exported(run_id: int):
    st.session_state["exported_run_id"] = run_id


def render(*, review_complete: bool, exported: bool):
    st.markdown("<div class='ll-kicker'>AUDITABLE RUNS</div>", unsafe_allow_html=True)
    st.title("Reconciliation history")
    st.markdown("Open a saved run and download its transaction-level reconciliation report.")
    runs = db.runs()
    render_stepper("Export", uploaded=True, validated=True, has_run=bool(runs), review_complete=review_complete, exported=exported)
    if not runs:
        st.info("Completed reconciliations will appear here. Start by uploading the two source files.")
        return
    history = pd.DataFrame([{"Run": run.id, "Created": run.created_at.strftime("%d %b %Y %H:%M UTC"), "Ledger file": run.ledger_filename, "Bank file": run.bank_filename, "Ledger rows": run.ledger_count, "Bank rows": run.bank_count} for run in runs])
    st.dataframe(history, use_container_width=True, hide_index=True)
    preferred = st.session_state.get("latest_run")
    default_index = next((idx for idx, run in enumerate(runs) if run.id == preferred), 0)
    selected = st.selectbox("Open run", runs, index=default_index, format_func=lambda run: f"Run #{run.id} · {run.ledger_filename}", key="history_run_id")
    try:
        with st.spinner("Loading the saved reconciliation report…"):
            report = report_frame(selected.id)
        if not report.empty:
            counts = report["status"].value_counts()
            columns = st.columns(min(4, max(1, len(counts))))
            for column, (label, count) in zip(columns, counts.items()):
                with column: metric(label, f"{count:,}")
            st.dataframe(report, use_container_width=True, hide_index=True)
            st.download_button("Download reconciliation report", report.to_csv(index=False).encode("utf-8-sig"), file_name=f"ledgerlens_run_{selected.id}.csv", mime="text/csv", type="primary", on_click=_mark_exported, args=(selected.id,), key="download_report")
        else:
            st.info("This saved run has no report rows.")
    except Exception:
        logger.exception("Unable to load report for run %s", selected.id)
        st.error("LedgerLens could not load this report. Check the application log and try again.")
