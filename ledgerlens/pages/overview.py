from __future__ import annotations

import pandas as pd
import streamlit as st

from ledgerlens.components import metric, navigate, render_stepper
from ledgerlens.service import dashboard_metrics


def render(*, first_run: bool, welcome: bool, on_get_started, on_sample_data, on_dismiss, review_complete: bool, exported: bool):
    stats = dashboard_metrics()
    render_stepper("Upload", uploaded=False, validated=False, has_run=bool(stats["runs"]), review_complete=review_complete, exported=exported)
    if first_run and welcome:
        from ledgerlens.components import welcome_screen
        welcome_screen(on_get_started, on_sample_data, on_dismiss)
        return
    if welcome:
        from ledgerlens.components import welcome_screen
        welcome_screen(on_get_started, on_sample_data, on_dismiss)
        return
    st.markdown("<div class='ll-kicker'>PORTFOLIO VIEW</div>", unsafe_allow_html=True)
    st.title("Reconciliation overview")
    st.markdown("Monitor reconciliation performance and see what needs attention.")
    cta, _ = st.columns([1.5, 5])
    with cta:
        if st.button("New reconciliation", type="primary", use_container_width=True): navigate("Upload & reconcile")
    columns = st.columns(4)
    with columns[0]: metric("Total transactions", f"{stats['total_transactions']:,}", f"{stats['ledger_count']:,} ledger · {stats['bank_count']:,} bank")
    with columns[1]: metric("Matched", f"{stats['matched_pct']:.1f}%", f"{stats['matched']:,} transaction pairs", tone="green")
    with columns[2]: metric("Unmatched", f"{stats['unmatched']:,}", "Exceptions requiring review", tone="yellow")
    with columns[3]: metric("Discrepancy value", f"{stats['discrepancy_value']:,.2f}", "Amount deltas + one-sided records", tone="pink")
    st.caption("Discrepancy value sums absolute amount differences and one-sided missing transaction amounts in the source currency units. Duplicate and invalid records are excluded.")
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Status breakdown")
        data = pd.DataFrame({"Status": list(stats["status_counts"]), "Transactions": list(stats["status_counts"].values())})
        if not data.empty: st.bar_chart(data.set_index("Status"), color="#285f93", height=280)
        else: st.info("Your first reconciliation will add status results here.")
    with right:
        st.subheader("Recent activity")
        if stats["runs"]:
            for run in stats["runs"][:5]:
                st.markdown(f"<div class='ll-welcome-step'><b>Run #{run.id} · {run.ledger_filename}</b><p>{run.created_at.strftime('%d %b %Y, %H:%M')} · {run.ledger_count:,} ledger / {run.bank_count:,} bank records</p></div>", unsafe_allow_html=True)
        else:
            st.info("No runs yet. Start with your own CSVs or use the sample walkthrough.")
