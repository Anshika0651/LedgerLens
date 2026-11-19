from __future__ import annotations

import pandas as pd

STATUSES = ["Matched", "Missing from bank", "Missing from ledger", "Amount mismatch", "Date mismatch", "Duplicate transaction", "Invalid data"]


def reconcile(ledger: pd.DataFrame, bank: pd.DataFrame, tolerance: float = 0.01) -> pd.DataFrame:
    """Return one result per source row; duplicates and malformed rows remain visible."""
    l = ledger.copy().reset_index(drop=True)
    b = bank.copy().reset_index(drop=True)
    l["_side"] = "ledger"; b["_side"] = "bank"
    l["_used"] = False; b["_used"] = False
    ldup = set(l.loc[l["transaction_id"].duplicated(False), "transaction_id"].dropna().astype(str))
    bdup = set(b.loc[b["transaction_id"].duplicated(False), "transaction_id"].dropna().astype(str))
    results = []
    def emit(lr, br, status, detail=""):
        results.append({"transaction_id": (lr if lr is not None else br).get("transaction_id"), "ledger": lr, "bank": br, "status": status, "detail": detail})
    for i, row in l.iterrows():
        if bool(row.get("_invalid", False)):
            l.at[i, "_used"] = True; emit(row, None, "Invalid data", "Ledger row contains a missing ID, invalid date, or invalid amount.")
    for i, row in b.iterrows():
        if bool(row.get("_invalid", False)):
            b.at[i, "_used"] = True; emit(None, row, "Invalid data", "Bank row contains a missing ID, invalid date, or invalid amount.")
    for i, row in l.iterrows():
        if l.at[i, "_used"]: continue
        tid = str(row["transaction_id"])
        if tid in ldup or tid in bdup:
            l.at[i, "_used"] = True
            matches = b.index[(b["transaction_id"].astype(str) == tid) & ~b["_used"]]
            if len(matches):
                j = int(matches[0]); b.at[j, "_used"] = True; emit(row, b.loc[j], "Duplicate transaction", "Duplicate transaction ID in one or both source files.")
            else: emit(row, None, "Duplicate transaction", "Duplicate transaction ID in source file.")
            continue
        matches = b.index[(b["transaction_id"].astype(str) == tid) & ~b["_used"]]
        l.at[i, "_used"] = True
        if not len(matches): emit(row, None, "Missing from bank", "Ledger transaction was not found in the bank statement."); continue
        j = int(matches[0]); other = b.loc[j]; b.at[j, "_used"] = True
        if abs(float(row.amount) - float(other.amount)) > tolerance:
            emit(row, other, "Amount mismatch", f"Ledger {float(row.amount):.2f}; bank {float(other.amount):.2f}.")
        elif pd.Timestamp(row.date).date() != pd.Timestamp(other.date).date():
            emit(row, other, "Date mismatch", f"Ledger date {pd.Timestamp(row.date).date()}; bank date {pd.Timestamp(other.date).date()}.")
        else: emit(row, other, "Matched")
    for j, row in b.iterrows():
        if b.at[j, "_used"]: continue
        tid = str(row["transaction_id"]); b.at[j, "_used"] = True
        if tid in bdup:
            emit(None, row, "Duplicate transaction", "Duplicate transaction ID in bank source file.")
        else: emit(None, row, "Missing from ledger", "Bank transaction was not found in the company ledger.")
    return pd.DataFrame(results, columns=["transaction_id", "ledger", "bank", "status", "detail"])
