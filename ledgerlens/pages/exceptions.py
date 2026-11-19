from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import streamlit as st

from ledgerlens import database as db
from ledgerlens.components import render_stepper

logger = logging.getLogger(__name__)
DISPOSITIONS = ["Confirmed as a valid exception", "Ledger corrected", "Bank record corrected", "Accepted difference", "Other resolution"]


def _amounts(row):
    values = []
    for record in (row.get("ledger") or {}, row.get("bank") or {}):
        try:
            amount = float(record.get("amount"))
            if pd.notna(amount): values.append(amount)
        except (TypeError, ValueError):
            continue
    return values


def render(*, review_complete: bool, exported: bool):
    st.markdown("<div class='ll-kicker'>INVESTIGATION WORKSPACE</div>", unsafe_allow_html=True)
    st.title("Exception management")
    st.markdown("Filter flagged records, compare the source entries, and record a decision with a required note.")
    runs = db.runs()
    if not runs:
        render_stepper("Review exceptions", uploaded=False, validated=False, has_run=False, review_complete=False, exported=False)
        st.info("Complete a reconciliation before exceptions can be reviewed.")
        return

    selected_run = st.selectbox("Reconciliation run", runs, format_func=lambda run: f"Run #{run.id} · {run.ledger_filename} · {run.created_at.strftime('%d %b %Y %H:%M')}", key="exception_run")
    _, rows = db.run_detail(selected_run.id)
    exceptions = [row for row in rows if row["status"] != "Matched"]
    done = all(row["resolution"] for row in exceptions)
    render_stepper("Review exceptions", uploaded=True, validated=True, has_run=True, review_complete=done, exported=exported)
    if not exceptions:
        st.success("This run has no exceptions. You can continue to export the report.")
        return

    all_types = sorted({row["status"] for row in exceptions})
    amounts = [amount for row in exceptions for amount in _amounts(row)]
    dates = []
    for row in exceptions:
        for record in (row.get("ledger") or {}, row.get("bank") or {}):
            parsed = pd.to_datetime(record.get("date"), errors="coerce")
            if pd.notna(parsed): dates.append(parsed.date())

    f1, f2, f3 = st.columns([1.2, 1, 1.5])
    with f1: selected_types = st.multiselect("Exception type", all_types, default=all_types)
    with f2: resolution_filter = st.selectbox("Review status", ["All", "Open", "Resolved"])
    with f3:
        if dates:
            date_filter = st.date_input("Transaction date range", value=(min(dates), max(dates)), min_value=min(dates), max_value=max(dates), key=f"date_range_{selected_run.id}")
        else:
            date_filter = ()
    amount_min, amount_max = (min(amounts), max(amounts)) if amounts else (0.0, 0.0)
    amount_range = st.slider("Amount range (either source record)", min_value=float(amount_min), max_value=float(amount_max if amount_max > amount_min else amount_min + 0.01), value=(float(amount_min), float(amount_max if amount_max > amount_min else amount_min + 0.01),), step=0.01, key=f"amount_range_{selected_run.id}")
    search = st.text_input("Search transaction ID or description", key=f"exception_search_{selected_run.id}")

    filtered = []
    for row in exceptions:
        if row["status"] not in selected_types: continue
        is_resolved = bool(row["resolution"])
        if resolution_filter == "Open" and is_resolved: continue
        if resolution_filter == "Resolved" and not is_resolved: continue
        row_amounts = _amounts(row)
        if amounts and row_amounts and not any(amount_range[0] <= amount <= amount_range[1] for amount in row_amounts): continue
        row_dates = []
        for record in (row.get("ledger") or {}, row.get("bank") or {}):
            parsed = pd.to_datetime(record.get("date"), errors="coerce")
            if pd.notna(parsed): row_dates.append(parsed.date())
        if len(date_filter) == 2 and row_dates and not any(date_filter[0] <= value <= date_filter[1] for value in row_dates): continue
        text = " ".join([str(row["transaction_id"]), str((row.get("ledger") or {}).get("description", "")), str((row.get("bank") or {}).get("description", ""))]).lower()
        if search and search.lower() not in text: continue
        filtered.append((row, min(row_dates) if row_dates else date.min, max(row_amounts) if row_amounts else 0.0))

    sort_col, sort_dir = st.columns([1, 1])
    with sort_col: sort_by = st.selectbox("Sort results by", ["Date", "Transaction ID", "Exception type", "Amount"])
    with sort_dir: descending = st.toggle("Descending", value=False)
    sort_keys = {"Date": lambda item: item[1], "Transaction ID": lambda item: str(item[0]["transaction_id"]), "Exception type": lambda item: item[0]["status"], "Amount": lambda item: item[2]}
    filtered.sort(key=sort_keys[sort_by], reverse=descending)
    st.caption(f"{len(filtered):,} matching exceptions · {sum(not item[0]['resolution'] for item in filtered):,} open")
    table = pd.DataFrame([{"Transaction ID": item[0]["transaction_id"], "Exception type": item[0]["status"], "Ledger date": (item[0].get("ledger") or {}).get("date"), "Ledger amount": (item[0].get("ledger") or {}).get("amount"), "Bank date": (item[0].get("bank") or {}).get("date"), "Bank amount": (item[0].get("bank") or {}).get("amount"), "Review status": "Resolved" if item[0]["resolution"] else "Open"} for item in filtered])
    if not table.empty: st.dataframe(table, use_container_width=True, hide_index=True)
    if not filtered:
        st.info("No exceptions match these filters. Try widening the amount or date range.")
        return

    choice = st.selectbox("Open an exception", [item[0] for item in filtered], format_func=lambda row: f"{row['transaction_id']} · {row['status']}" + (" · Resolved" if row["resolution"] else " · Open"), key=f"exception_choice_{selected_run.id}")
    st.markdown(f"### {choice['transaction_id']} · {choice['status']}")
    st.info(choice["detail"] or "The source records did not meet the reconciliation matching rules.")
    ledger_col, bank_col = st.columns(2)
    for column, title, record in ((ledger_col, "Company ledger", choice.get("ledger")), (bank_col, "Bank statement", choice.get("bank"))):
        with column:
            st.markdown(f"**{title}**")
            if record: st.json({key: value for key, value in record.items() if not key.startswith("_")})
            else: st.info("No corresponding source record.")

    if choice["resolution"]:
        st.success("Current saved resolution")
        st.markdown(choice["resolution"])
        if choice.get("resolution_at"): st.caption(f"Saved {choice['resolution_at']} · {choice.get('resolved_by') or 'User'}")
        st.caption("The current database model keeps one resolution per exception. Earlier edits are not retained as history.")
    with st.form(f"resolve_{choice['id']}"):
        status = st.selectbox("Resolution status", DISPOSITIONS, help="The selected disposition is stored together with the note in the existing resolution note field.")
        note = st.text_area("Resolution note (required)", placeholder="Describe what you checked and why this disposition is appropriate.")
        submitted = st.form_submit_button("Save resolution", type="primary")
        if submitted:
            if not note.strip(): st.error("Enter a resolution note before saving.")
            else:
                try:
                    db.resolve(choice["id"], f"{status} — {note.strip()}")
                    st.success("Resolution saved.")
                    st.rerun()
                except Exception:
                    logger.exception("Unable to save exception resolution %s", choice["id"])
                    st.error("The resolution could not be saved. Check the application log and try again.")
