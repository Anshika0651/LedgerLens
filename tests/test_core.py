import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ledgerlens import database as db
from ledgerlens.onboarding import should_show_welcome
from ledgerlens.reconciliation import reconcile
from ledgerlens.sample_data import generate_onboarding_sample
from ledgerlens.service import dashboard_metrics
from ledgerlens.validation import validate_csv


def frame(rows):
    result = pd.DataFrame(rows)
    result["date"] = pd.to_datetime(result["date"])
    result["source_row"] = range(2, len(result) + 2)
    result["_invalid"] = False
    return result


def test_reconcile_classifies_all_core_cases():
    ledger = frame([
        {"transaction_id": "same", "date": "2025-01-01", "amount": 10, "description": "a"},
        {"transaction_id": "amt", "date": "2025-01-01", "amount": 10, "description": "b"},
        {"transaction_id": "date", "date": "2025-01-01", "amount": 10, "description": "c"},
        {"transaction_id": "ledger-only", "date": "2025-01-01", "amount": 5, "description": "d"},
    ])
    bank = frame([
        {"transaction_id": "same", "date": "2025-01-01", "amount": 10, "description": "a"},
        {"transaction_id": "amt", "date": "2025-01-01", "amount": 11, "description": "b"},
        {"transaction_id": "date", "date": "2025-01-03", "amount": 10, "description": "c"},
        {"transaction_id": "bank-only", "date": "2025-01-01", "amount": 2, "description": "e"},
    ])
    result = reconcile(ledger, bank)
    assert result.status.tolist() == ["Matched", "Amount mismatch", "Date mismatch", "Missing from bank", "Missing from ledger"]


def test_duplicate_ids_are_flagged_and_not_matched():
    ledger = frame([{"transaction_id": "dup", "date": "2025-01-01", "amount": 1}, {"transaction_id": "dup", "date": "2025-01-01", "amount": 1}])
    bank = frame([{"transaction_id": "dup", "date": "2025-01-01", "amount": 1}])
    assert set(reconcile(ledger, bank).status) == {"Duplicate transaction"}


def test_validation_reports_bad_rows_and_duplicate_ids():
    csv = b"transaction_id,date,amount\nA,2025-01-01,2\nA,not-a-date,NaN\n"
    result = validate_csv(csv, "test.csv")
    assert not result.errors
    assert result.duplicate_ids == ["A"]
    assert result.invalid_rows == [3]
    assert len(result.frame) == 2


def test_validation_rejects_missing_columns():
    result = validate_csv(b"id,amount\nA,3\n", "bad.csv")
    assert result.errors and "transaction_id" in result.errors[0]


def test_validation_gives_actionable_message_for_empty_file():
    result = validate_csv(b"", "empty.csv")
    assert result.errors
    assert "no header row" in result.errors[0]
    assert "transaction_id, date, and amount" in result.errors[0]


def test_validation_messages_are_actionable_and_blank_rows_are_retained():
    missing = validate_csv(b"transaction_id,date,amount\nA,not-a-date,nope\n\n", "bad.csv")
    assert missing.valid
    assert len(missing.frame) == 2
    assert any("invalid dates" in warning and "YYYY-MM-DD" in warning for warning in missing.warnings)
    assert any("non-numeric amounts" in warning and "125.50" in warning for warning in missing.warnings)
    assert any("empty row(s)" in warning and "Remove blank lines" in warning for warning in missing.warnings)


def test_validation_blocks_duplicate_normalized_headers():
    result = validate_csv(b"transaction_id, Transaction_ID,date,amount\nA,A,2025-01-01,3\n", "duplicate-header.csv")
    assert result.errors
    assert "Duplicate column names" in result.errors[0]


def test_first_run_detection_respects_existing_runs_and_dismissal():
    assert should_show_welcome(0)
    assert not should_show_welcome(0, dismissed=True)
    assert not should_show_welcome(1)


def test_onboarding_sample_is_deterministic_and_covers_supported_statuses():
    ledger_csv, bank_csv = generate_onboarding_sample(seed=99)
    assert (ledger_csv, bank_csv) == generate_onboarding_sample(seed=99)
    ledger = validate_csv(ledger_csv, "sample-ledger.csv")
    bank = validate_csv(bank_csv, "sample-bank.csv")
    statuses = set(reconcile(ledger.frame, bank.frame)["status"])
    assert statuses == {"Matched", "Missing from bank", "Missing from ledger", "Amount mismatch", "Date mismatch", "Duplicate transaction"}


def test_dashboard_metrics_use_saved_results(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'metrics.db'}", future=True)
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "Session", sessionmaker(bind=engine, expire_on_commit=False))
    ledger_csv, bank_csv = generate_onboarding_sample()
    ledger = validate_csv(ledger_csv, "synthetic-ledger.csv")
    bank = validate_csv(bank_csv, "synthetic-bank.csv")
    db.create_run("synthetic-ledger.csv", "synthetic-bank.csv", ledger.frame.to_dict("records"), bank.frame.to_dict("records"), reconcile(ledger.frame, bank.frame).to_dict("records"))
    metrics = dashboard_metrics()
    assert metrics["total_transactions"] == 11
    assert metrics["matched"] == 1
    assert metrics["unmatched"] == 6
    assert metrics["discrepancy_value"] == pytest.approx(89.5)
    engine.dispose()


def test_result_rows_persist_and_can_be_resolved(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "Session", sessionmaker(bind=engine, expire_on_commit=False))
    ledger = frame([{"transaction_id": "A", "date": "2025-01-01", "amount": 3, "description": "ledger"}])
    bank = frame([{"transaction_id": "B", "date": "2025-01-01", "amount": 4, "description": "bank"}])
    result_rows = reconcile(ledger, bank).to_dict("records")
    run_id = db.create_run("ledger.csv", "bank.csv", ledger.to_dict("records"), bank.to_dict("records"), result_rows)
    run, saved = db.run_detail(run_id)
    assert run.ledger_count == 1 and run.bank_count == 1
    assert [row["status"] for row in saved] == ["Missing from bank", "Missing from ledger"]
    db.resolve(saved[0]["id"], "Confirmed timing issue")
    _, saved_again = db.run_detail(run_id)
    assert saved_again[0]["resolution"] == "Confirmed timing issue"
    engine.dispose()
