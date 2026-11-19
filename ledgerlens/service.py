from __future__ import annotations

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from . import database as db
from .database import create_run, run_detail
from .reconciliation import reconcile


def reconcile_and_save(ledger_validation, bank_validation, ledger_name: str, bank_name: str) -> int:
    if ledger_validation.errors or bank_validation.errors:
        raise ValueError("Correct the file format errors before reconciling.")
    results = reconcile(ledger_validation.frame, bank_validation.frame)
    return create_run(ledger_name, bank_name, ledger_validation.frame.to_dict("records"), bank_validation.frame.to_dict("records"), results.to_dict("records"))


def run_sample_reconciliation() -> int:
    from .sample_data import generate_onboarding_sample
    from .validation import validate_csv

    ledger_csv, bank_csv = generate_onboarding_sample()
    ledger = validate_csv(ledger_csv, "synthetic_onboarding_ledger.csv")
    bank = validate_csv(bank_csv, "synthetic_onboarding_bank.csv")
    return reconcile_and_save(ledger, bank, "synthetic_onboarding_ledger.csv", "synthetic_onboarding_bank.csv")


def report_frame(run_id: int) -> pd.DataFrame:
    run, rows = run_detail(run_id)
    if not run: return pd.DataFrame()
    records = []
    for row in rows:
        l, b = row["ledger"] or {}, row["bank"] or {}
        records.append({"transaction_id": row["transaction_id"], "status": row["status"], "detail": row["detail"], "ledger_date": l.get("date"), "ledger_amount": l.get("amount"), "ledger_description": l.get("description"), "bank_date": b.get("date"), "bank_amount": b.get("amount"), "bank_description": b.get("description"), "resolution_note": row["resolution"]})
    return pd.DataFrame(records)


def dashboard_metrics():
    """Read live persisted metrics without caching or loading transaction JSON blobs."""
    with db.Session() as session:
        runs = list(session.scalars(select(db.ReconciliationRun).order_by(db.ReconciliationRun.created_at.desc())))
        status_counts = dict(session.execute(select(db.ReconciliationResult.status, func.count()).group_by(db.ReconciliationResult.status)).all())
        total_transactions = sum(run.ledger_count + run.bank_count for run in runs)
        total_l = sum(run.ledger_count for run in runs)
        total_b = sum(run.bank_count for run in runs)
        matched = status_counts.get("Matched", 0)
        result_count = sum(status_counts.values())
        mismatch_delta = 0.0
        one_sided_value = 0.0
        ledger_tx = aliased(db.Transaction)
        bank_tx = aliased(db.Transaction)
        rows = session.execute(
            select(db.ReconciliationResult.status, ledger_tx.amount, bank_tx.amount)
            .outerjoin(ledger_tx, db.ReconciliationResult.ledger_transaction_id == ledger_tx.id)
            .outerjoin(bank_tx, db.ReconciliationResult.bank_transaction_id == bank_tx.id)
        ).all()
        for status, ledger_amount, bank_amount in rows:
            if status == "Amount mismatch": mismatch_delta += abs((ledger_amount or 0) - (bank_amount or 0))
            elif status == "Missing from bank": one_sided_value += abs(ledger_amount or 0)
            elif status == "Missing from ledger": one_sided_value += abs(bank_amount or 0)
    return {
        "runs": runs,
        "status_counts": status_counts,
        "total_transactions": total_transactions,
        "ledger_count": total_l,
        "bank_count": total_b,
        "matched": matched,
        "matched_pct": (matched / result_count * 100) if result_count else 0.0,
        "unmatched": sum(count for status, count in status_counts.items() if status != "Matched"),
        "discrepancy_value": mismatch_delta + one_sided_value,
    }
