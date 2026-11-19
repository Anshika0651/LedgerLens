"""Generate reproducible synthetic ledger and bank CSV fixtures."""
from pathlib import Path
import csv
import io
import random
from datetime import date, timedelta


def generate(output_dir="data", n=600, seed=42):
    rng = random.Random(seed)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 1)
    ledger = [{"transaction_id": f"TXN-{i:05}", "date": (start + timedelta(days=i - 1)).isoformat(), "amount": f"{rng.uniform(12, 12000):.2f}", "description": f"Synthetic supplier payment {i:04}"} for i in range(1, n + 1)]
    bank = [dict(row) for row in ledger]
    # Deterministic exception mix; every source still has at least 500 rows.
    bank = [row for ix, row in enumerate(bank) if ix not in range(20, 35)]
    for ix in range(40, 52): bank[ix]["amount"] = f"{float(bank[ix]['amount']) + 27.50:.2f}"
    for ix in range(60, 70): bank[ix]["date"] = (date.fromisoformat(bank[ix]["date"]) + timedelta(days=2)).isoformat()
    bank.extend(dict(row) for row in ledger[100:112])
    for i, row in enumerate(ledger[200:215], start=1): bank.append({**row, "transaction_id": f"BNK-ONLY-{i:03}"})
    fields = ["transaction_id", "date", "amount", "description"]
    for name, rows in (("synthetic_ledger.csv", ledger), ("synthetic_bank_statement.csv", bank)):
        with (out / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return ledger, bank


def generate_onboarding_sample(seed=42):
    """Build a small deterministic in-memory example exercising existing statuses."""
    rng = random.Random(seed)
    matched = round(rng.uniform(80, 140), 2)
    amount_ledger = round(rng.uniform(50, 90), 2)
    date_amount = round(rng.uniform(20, 60), 2)
    duplicate_amount = round(rng.uniform(10, 30), 2)
    ledger = [
        {"transaction_id": "DEMO-001", "date": "2025-01-06", "amount": f"{matched:.2f}", "description": "Synthetic · matched supplier payment"},
        {"transaction_id": "DEMO-002", "date": "2025-01-07", "amount": "45.00", "description": "Synthetic · missing from bank"},
        {"transaction_id": "DEMO-003", "date": "2025-01-08", "amount": f"{amount_ledger:.2f}", "description": "Synthetic · amount mismatch"},
        {"transaction_id": "DEMO-004", "date": "2025-01-09", "amount": f"{date_amount:.2f}", "description": "Synthetic · date mismatch"},
        {"transaction_id": "DEMO-005", "date": "2025-01-10", "amount": f"{duplicate_amount:.2f}", "description": "Synthetic · duplicate ID, first row"},
        {"transaction_id": "DEMO-005", "date": "2025-01-10", "amount": f"{duplicate_amount:.2f}", "description": "Synthetic · duplicate ID, second row"},
    ]
    bank = [
        {"transaction_id": "DEMO-001", "date": "2025-01-06", "amount": f"{matched:.2f}", "description": "Synthetic · matched supplier payment"},
        {"transaction_id": "DEMO-003", "date": "2025-01-08", "amount": f"{amount_ledger + 12.50:.2f}", "description": "Synthetic · amount mismatch"},
        {"transaction_id": "DEMO-004", "date": "2025-01-11", "amount": f"{date_amount:.2f}", "description": "Synthetic · date mismatch"},
        {"transaction_id": "DEMO-005", "date": "2025-01-10", "amount": f"{duplicate_amount:.2f}", "description": "Synthetic · duplicate ID"},
        {"transaction_id": "DEMO-006", "date": "2025-01-12", "amount": "32.00", "description": "Synthetic · missing from ledger"},
    ]
    def to_csv(rows):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=["transaction_id", "date", "amount", "description"])
        writer.writeheader(); writer.writerows(rows)
        return buffer.getvalue().encode("utf-8")
    return to_csv(ledger), to_csv(bank)


if __name__ == "__main__": generate()
