from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from ledgerlens.validation import ValidationResult

PAGE_UPLOAD = "Upload & reconcile"
PAGE_EXCEPTIONS = "Exceptions"
PAGE_HISTORY = "History"


def navigate(page: str):
    st.query_params["page"] = page
    st.rerun()


def metric(label: str, value: str, note: str = "", tone: str = "neutral"):
    tone_class = {"green": "ll-metric-green", "pink": "ll-metric-pink", "yellow": "ll-metric-yellow", "blue": "ll-metric-blue"}.get(tone, "")
    help_html = f"<div class='ll-metric-note'>{note}</div>" if note else ""
    st.markdown(f"<div class='ll-metric {tone_class}'><div class='ll-metric-label'>{label}</div><div class='ll-metric-value'>{value}</div>{help_html}</div>", unsafe_allow_html=True)


def render_stepper(current: str, *, uploaded: bool, validated: bool, has_run: bool, review_complete: bool, exported: bool):
    steps = [
        ("Upload", PAGE_UPLOAD, True, uploaded or has_run, "Choose both source CSVs."),
        ("Validate", PAGE_UPLOAD, uploaded or has_run, validated or has_run, "Upload both files first."),
        ("Reconcile", PAGE_UPLOAD, validated or has_run, has_run, "Resolve blocking file errors first."),
        ("Review exceptions", PAGE_EXCEPTIONS, has_run, review_complete, "Complete a reconciliation first."),
        ("Export", PAGE_HISTORY, has_run, exported, "Complete a reconciliation first."),
    ]
    columns = st.columns(len(steps))
    for column, (name, page, enabled, done, reason) in zip(columns, steps):
        active = name == current
        prefix = "✓ " if done else ("› " if active else "○ ")
        with column:
            if st.button(prefix + name, key=f"step_{name}", disabled=not enabled, help=None if enabled else reason, use_container_width=True, type="primary" if active else "secondary"):
                navigate(page)
    st.caption(f"Current step: **{current}**. Steps become available as you complete their prerequisites.")
    st.divider()


def render_validation(label: str, result: ValidationResult):
    with st.container(border=True):
        st.markdown(f"**{label}** · {len(result.frame):,} transaction rows")
        if result.errors:
            st.markdown("**Action needed before continuing**")
            for error in result.errors: st.error(error)
        elif result.warnings:
            st.markdown("**Review these data warnings**")
            for warning in result.warnings: st.warning(warning)
        else:
            st.success("File structure and transaction rows look good.")
        if not result.frame.empty:
            preview = result.frame.drop(columns=["_invalid"], errors="ignore").head(8)
            st.dataframe(preview, use_container_width=True, hide_index=True)
            st.caption(f"Previewing up to 8 of {len(result.frame):,} rows.")


def welcome_screen(on_get_started: Callable, on_sample_data: Callable, on_dismiss: Callable):
    st.markdown("<div class='ll-kicker'>FINANCIAL OPERATIONS WORKSPACE</div>", unsafe_allow_html=True)
    st.title("Welcome to LedgerLens")
    st.markdown("Compare company ledger activity with bank transactions, investigate exceptions, and keep a record of each reconciliation.")
    cols = st.columns(3)
    for col, number, title, desc, tone in zip(cols, ["01", "02", "03"], ["Upload", "Reconcile", "Review"], ["Add a ledger and bank CSV.", "Validate the files and compare transaction IDs.", "Resolve exceptions and export the report."], ["green", "yellow", "pink"]):
        with col:
            st.markdown(f"<div class='ll-welcome-step ll-welcome-step-{tone}'><span>{number}</span><b>{title}</b><p>{desc}</p></div>", unsafe_allow_html=True)
    st.write("")
    left, right, later, _ = st.columns([1.35, 1.55, 1.1, 1.9])
    with left:
        if st.button("Get started", type="primary", use_container_width=True): on_get_started()
    with right:
        if st.button("Try with sample data", use_container_width=True): on_sample_data()
    with later:
        if st.button("Not now", use_container_width=True): on_dismiss()
    st.caption("Sample data is synthetic and demonstrates the exception types supported by the current reconciliation engine.")


def template_bytes() -> bytes:
    return b"transaction_id,date,amount,description\r\n"


def status_badge(status: str) -> str:
    mapping = {
        "Matched": "ll-status-good",
        "Amount mismatch": "ll-status-warn",
        "Date mismatch": "ll-status-warn",
        "Duplicate transaction": "ll-status-warn",
        "Invalid data": "ll-status-bad",
        "Missing from bank": "ll-status-bad",
        "Missing from ledger": "ll-status-bad",
    }
    return f"<span class='{mapping.get(status, 'll-status-neutral')}'>{status}</span>"
