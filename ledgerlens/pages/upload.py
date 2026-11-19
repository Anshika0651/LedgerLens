from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from ledgerlens.components import metric, navigate, render_stepper, render_validation, template_bytes
from ledgerlens.database import run_detail
from ledgerlens.service import reconcile_and_save, report_frame, run_sample_reconciliation
from ledgerlens.validation import validate_csv

logger = logging.getLogger(__name__)


def render(*, has_run: bool, review_complete: bool, exported: bool):
    st.markdown("<div class='ll-kicker'>IMPORT AND COMPARE</div>", unsafe_allow_html=True)
    st.title("Upload & reconcile")
    st.markdown("Add a company ledger and a bank statement. LedgerLens validates both files before enabling reconciliation.")

    col_l, col_b = st.columns(2)
    with col_l:
        st.markdown("**Company ledger**")
        ledger_file = st.file_uploader("Upload ledger CSV", type=["csv"], key="ledger")
        st.download_button("Download ledger template", template_bytes(), file_name="ledger_template.csv", mime="text/csv", key="ledger_template")
        st.caption("Required: transaction_id, date (YYYY-MM-DD), amount. Optional: description.")
    with col_b:
        st.markdown("**Bank statement**")
        bank_file = st.file_uploader("Upload bank CSV", type=["csv"], key="bank")
        st.download_button("Download bank template", template_bytes(), file_name="bank_statement_template.csv", mime="text/csv", key="bank_template")
        st.caption("Use the same required headers. Amounts must be finite numbers, such as 125.50.")

    has_both = ledger_file is not None and bank_file is not None
    ledger_result = bank_result = None
    if has_both:
        with st.spinner("Checking the uploaded files…"):
            ledger_result = validate_csv(ledger_file, ledger_file.name)
            bank_result = validate_csv(bank_file, bank_file.name)
    blocking_free = bool(has_both and ledger_result.valid and bank_result.valid)
    st.session_state["upload_files_present"] = has_both
    st.session_state["upload_validation_passed"] = blocking_free
    current = "Upload" if not has_both else ("Reconcile" if blocking_free else "Validate")
    render_stepper(current, uploaded=has_both, validated=blocking_free, has_run=has_run, review_complete=review_complete, exported=exported)

    if not has_both:
        st.info("Upload both files to see record counts and validation results. You can also use the synthetic sample from the welcome screen.")
        if st.button("Use the small synthetic sample", help="Creates and saves a demonstration reconciliation with every supported status."):
            try:
                with st.status("Running the sample reconciliation…", expanded=True) as status:
                    run_id = run_sample_reconciliation()
                    st.session_state["latest_run"] = run_id
                    st.session_state["onboarding_dismissed"] = True
                    status.update(label="Sample reconciliation is ready", state="complete", expanded=False)
                st.rerun()
            except Exception:
                logger.exception("Sample reconciliation failed")
                st.error("The sample reconciliation could not be completed. Check the application log and try again.")
        return

    st.subheader("File checks")
    with st.expander("Company ledger validation", expanded=True): render_validation("Company ledger", ledger_result)
    with st.expander("Bank statement validation", expanded=True): render_validation("Bank statement", bank_result)
    if not blocking_free:
        st.error("Reconciliation is paused until both CSV files have the required columns and at least one transaction row.")
    else:
        st.info("Row-level warnings are preserved as investigation items. Correct source data where possible; LedgerLens will not discard those rows.")
    reconcile_clicked = st.button("Reconcile files", type="primary", disabled=not blocking_free, use_container_width=True)
    if reconcile_clicked:
        try:
            with st.status("Reconciling transactions and saving the run…", expanded=True) as status:
                run_id = reconcile_and_save(ledger_result, bank_result, ledger_file.name, bank_file.name)
                st.session_state["latest_run"] = run_id
                st.session_state["onboarding_dismissed"] = True
                status.update(label=f"Run #{run_id} saved", state="complete", expanded=False)
            st.rerun()
        except Exception:
            logger.exception("Reconciliation save failed")
            st.error("LedgerLens could not save this reconciliation. Your source files are unchanged; check the application log and try again.")

    latest_run = st.session_state.get("latest_run")
    if latest_run:
        run, rows = run_detail(int(latest_run))
        if run:
            st.subheader(f"Run #{run.id} results")
            counts = pd.Series([row["status"] for row in rows]).value_counts()
            cols = st.columns(min(4, max(1, len(counts))))
            for column, (label, count) in zip(cols, counts.items()):
                with column: metric(label, f"{count:,}")
            st.dataframe(report_frame(run.id), use_container_width=True, hide_index=True)
            if st.button("Review exceptions", type="primary"):
                navigate("Exceptions")
