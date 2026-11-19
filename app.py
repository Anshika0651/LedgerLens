from __future__ import annotations

import logging

import streamlit as st
from sqlalchemy import func, select

from ledgerlens import database as db
from ledgerlens.components import navigate
from ledgerlens.onboarding import should_show_welcome
from ledgerlens.service import run_sample_reconciliation
from ledgerlens.ui import setup
from ledgerlens.pages import exceptions, history, overview, upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ledgerlens.app")

setup()

PAGES = ["Overview", "Upload & reconcile", "Exceptions", "History"]


def sync_navigation_query():
    st.query_params["page"] = st.session_state.get("navigation_page", "Overview")


def start_first_run():
    st.session_state["onboarding_dismissed"] = True
    st.session_state["onboarding_force_open"] = False
    navigate("Upload & reconcile")


def dismiss_welcome():
    st.session_state["onboarding_dismissed"] = True
    st.session_state["onboarding_force_open"] = False
    st.query_params["page"] = "Overview"
    st.rerun()


def try_sample_data():
    try:
        with st.status("Preparing and reconciling the synthetic example…", expanded=True) as status:
            run_id = run_sample_reconciliation()
            st.session_state["latest_run"] = run_id
            st.session_state["onboarding_dismissed"] = True
            st.session_state["onboarding_force_open"] = False
            status.update(label=f"Sample run #{run_id} is ready", state="complete", expanded=False)
        navigate("Upload & reconcile")
    except Exception:
        logger.exception("Onboarding sample run failed")
        st.error("The sample reconciliation could not be completed. Check the application log and try again.")


with st.sidebar:
    st.markdown("<div style='font-size:1.18rem;font-weight:700;letter-spacing:-.04em;padding:10px 0 1px'>Ledger<span style='color:#285f93'>Lens</span></div><div style='font-size:.76rem;color:#687887'>Financial operations</div>", unsafe_allow_html=True)
    st.divider()
    requested_page = st.query_params.get("page", "Overview")
    if requested_page not in PAGES: requested_page = "Overview"
    if st.session_state.get("navigation_page") != requested_page:
        st.session_state["navigation_page"] = requested_page
    page = st.radio("Workspace", PAGES, key="navigation_page", on_change=sync_navigation_query, label_visibility="collapsed")
    st.divider()
    with st.expander("Help & resources"):
        if st.button("Open welcome guide", use_container_width=True):
            st.session_state["onboarding_force_open"] = True
            st.query_params["page"] = "Overview"
            st.rerun()
        st.caption("CSV templates are available on Upload & reconcile.")
    st.caption("Data stays in your configured database.")

try:
    runs = db.runs()
except Exception:
    logger.exception("Could not load reconciliation runs")
    st.error("LedgerLens could not connect to its database. Check the DATABASE_URL and application log, then restart the app.")
    st.stop()

first_run = not runs
welcome = bool(st.session_state.get("onboarding_force_open")) or should_show_welcome(len(runs), bool(st.session_state.get("onboarding_dismissed")))
latest_run_id = st.session_state.get("latest_run")
if latest_run_id not in {run.id for run in runs}:
    latest_run_id = runs[0].id if runs else None
review_complete = False
if latest_run_id is not None:
    try:
        with db.Session() as session:
            total = session.scalar(select(func.count()).select_from(db.ReconciliationResult).where(db.ReconciliationResult.run_id == latest_run_id, db.ReconciliationResult.status != "Matched")) or 0
            resolved = session.scalar(select(func.count()).select_from(db.ReconciliationResult).join(db.ExceptionResolution).where(db.ReconciliationResult.run_id == latest_run_id, db.ReconciliationResult.status != "Matched")) or 0
            review_complete = resolved == total
    except Exception:
        logger.exception("Could not read exception completion state for run %s", latest_run_id)

exported = st.session_state.get("exported_run_id") == latest_run_id and latest_run_id is not None

try:
    if page == "Overview":
        overview.render(first_run=first_run, welcome=welcome, on_get_started=start_first_run, on_sample_data=try_sample_data, on_dismiss=dismiss_welcome, review_complete=review_complete, exported=exported)
    elif page == "Upload & reconcile":
        upload.render(has_run=bool(runs), review_complete=review_complete, exported=exported)
    elif page == "Exceptions":
        exceptions.render(review_complete=review_complete, exported=exported)
    elif page == "History":
        history.render(review_complete=review_complete, exported=exported)
except Exception:
    logger.exception("Page rendering failed for %s", page)
    st.error("LedgerLens could not load this page. Check the application log and refresh the browser.")
