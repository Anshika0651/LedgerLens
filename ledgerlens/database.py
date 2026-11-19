from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, DateTime, Float, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase): pass


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ledger_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    ledger_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bank_count: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[list["ReconciliationResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    transaction_date: Mapped[str] = mapped_column(String(32), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_runs.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    ledger_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    bank_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped["ExceptionResolution | None"] = relationship(back_populates="result", uselist=False, cascade="all, delete-orphan")
    run: Mapped[ReconciliationRun] = relationship(back_populates="results")


class ExceptionResolution(Base):
    __tablename__ = "exception_resolutions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_results.id"), unique=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_by: Mapped[str] = mapped_column(String(128), default="User")
    resolved_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    result: Mapped[ReconciliationResult] = relationship(back_populates="resolution")


def get_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///ledgerlens.db")
    return create_engine(url, future=True, pool_pre_ping=True)


engine = get_engine()
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def _json_value(value: Any):
    if hasattr(value, "isoformat"): return value.isoformat()
    if value is None: return None
    try:
        if value != value: return None
    except Exception: pass
    return value.item() if hasattr(value, "item") else str(value)


def _string(value):
    if value is None or str(value) in {"<NA>", "nan", "NaT"}: return ""
    try:
        if value != value: return ""
    except Exception: pass
    return str(value)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError): return None


def create_run(ledger_name: str, bank_name: str, ledger_rows: list[dict], bank_rows: list[dict], result_rows: list[dict]) -> int:
    with Session.begin() as session:
        run = ReconciliationRun(ledger_filename=ledger_name, bank_filename=bank_name, ledger_count=len(ledger_rows), bank_count=len(bank_rows))
        session.add(run); session.flush()
        source_map = {}
        for source, rows in (("ledger", ledger_rows), ("bank", bank_rows)):
            for row in rows:
                safe_row = {key: _json_value(value) for key, value in row.items()}
                record = Transaction(run_id=run.id, source=source, source_row=int(row.get("source_row", 0)), transaction_id=_string(row.get("transaction_id")), transaction_date=_string(row.get("date"))[:32], amount=_number(row.get("amount")), description=_string(row.get("description")), raw_json=json.dumps(safe_row, allow_nan=False))
                session.add(record); session.flush(); source_map[(source, int(row.get("source_row", 0)))] = record.id
        for item in result_rows:
            lr, br = item.get("ledger"), item.get("bank")
            session.add(ReconciliationResult(run_id=run.id, transaction_id=_string(item.get("transaction_id")), ledger_transaction_id=source_map.get(("ledger", int(lr.get("source_row", 0)))) if lr is not None else None, bank_transaction_id=source_map.get(("bank", int(br.get("source_row", 0)))) if br is not None else None, status=item["status"], detail=item.get("detail", "")))
        return run.id


def runs():
    with Session() as s: return list(s.scalars(select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc())))


def run_detail(run_id: int):
    with Session() as s:
        run = s.get(ReconciliationRun, run_id)
        if not run: return None, []
        result_rows = list(s.scalars(select(ReconciliationResult).where(ReconciliationResult.run_id == run_id).order_by(ReconciliationResult.id)))
        def txn(txid):
            t = s.get(Transaction, txid) if txid else None
            return json.loads(t.raw_json) if t else None
        output = [{"id": r.id, "transaction_id": r.transaction_id, "status": r.status, "detail": r.detail, "ledger": txn(r.ledger_transaction_id), "bank": txn(r.bank_transaction_id), "resolution": r.resolution.note if r.resolution else None, "resolution_at": r.resolution.resolved_at.isoformat() if r.resolution else None, "resolved_by": r.resolution.resolved_by if r.resolution else None} for r in result_rows]
        return run, output


def resolve(result_id: int, note: str, resolved_by: str = "User"):
    with Session.begin() as s:
        result = s.get(ReconciliationResult, result_id)
        if not result: raise ValueError("Exception no longer exists.")
        if result.resolution:
            result.resolution.note = note; result.resolution.resolved_by = resolved_by; result.resolution.resolved_at = datetime.now(timezone.utc)
        else: result.resolution = ExceptionResolution(note=note, resolved_by=resolved_by)
