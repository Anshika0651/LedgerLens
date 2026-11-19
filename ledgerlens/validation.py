from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path
from typing import Any

import pandas as pd
import math

REQUIRED_COLUMNS = {"transaction_id", "date", "amount"}
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    frame: pd.DataFrame
    errors: list[str]
    warnings: list[str]
    duplicate_ids: list[str]
    invalid_rows: list[int]

    @property
    def valid(self) -> bool:
        """True when the file structure is usable; row-level issues remain reviewable warnings."""
        return not self.errors and not self.frame.empty


def validate_csv(source: Any, filename: str = "upload.csv") -> ValidationResult:
    try:
        if isinstance(source, bytes): source = BytesIO(source)
        elif isinstance(source, Path): source = str(source)
        elif not isinstance(source, str): source = BytesIO(source.getvalue())
        frame = pd.read_csv(source, skip_blank_lines=False)
    except pd.errors.EmptyDataError:
        logger.exception("Uploaded CSV %s contains no header row", filename)
        return ValidationResult(pd.DataFrame(), [f"{filename} is empty or has no header row. Add the required transaction_id, date, and amount headers."], [], [], [])
    except Exception:
        logger.exception("Unable to read uploaded CSV %s", filename)
        return ValidationResult(pd.DataFrame(), [f"Could not read {filename}. Check that it is a readable CSV and try again."], [], [], [])
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    duplicates_header = sorted(set(frame.columns[frame.columns.duplicated()].astype(str)))
    if duplicates_header:
        names = ", ".join(duplicates_header)
        return ValidationResult(frame, [f"Duplicate column names after trimming and case normalization: {names}. Rename each column so headers are unique."], [], [], [])
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        return ValidationResult(frame, ["Missing required columns: " + ", ".join(missing) + ". Add these exact headers to the first row of the CSV."], [], [], [])
    if frame.empty:
        return ValidationResult(frame, ["This CSV has a header but no transaction rows. Add at least one transaction row."], [], [], [])
    frame["transaction_id"] = frame["transaction_id"].astype("string").str.strip()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.tz_convert(None)
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    empty_rows = frame[list(REQUIRED_COLUMNS)].isna().all(axis=1)
    bad_id = frame["transaction_id"].isna() | frame["transaction_id"].eq("")
    bad_date = frame["date"].isna()
    bad_amount = frame["amount"].isna() | ~frame["amount"].map(lambda x: math.isfinite(float(x)) if pd.notna(x) else False)
    invalid_mask = bad_id | bad_date | bad_amount
    invalid_rows = [int(i) + 2 for i in frame.index[invalid_mask]]
    duplicates = sorted(frame.loc[frame["transaction_id"].duplicated(keep=False) & ~bad_id, "transaction_id"].astype(str).unique())
    warnings = []
    if bool(empty_rows.any()):
        empty_nums = [str(int(i) + 2) for i in frame.index[empty_rows][:5]]
        suffix = "…" if int(empty_rows.sum()) > 5 else ""
        warnings.append(f"{int(empty_rows.sum())} empty row(s) at CSV row(s) {', '.join(empty_nums)}{suffix}. Remove blank lines or fill them in; they will remain visible as invalid data.")
    bad_dates = bad_date & ~empty_rows
    if bool(bad_dates.any()):
        rows = ", ".join(str(int(i) + 2) for i in frame.index[bad_dates][:5])
        warnings.append(f"{int(bad_dates.sum())} row(s) have missing or invalid dates (for example row {rows}). Use YYYY-MM-DD or another unambiguous date; these records will be retained as invalid data.")
    bad_amounts = bad_amount & ~empty_rows
    if bool(bad_amounts.any()):
        rows = ", ".join(str(int(i) + 2) for i in frame.index[bad_amounts][:5])
        warnings.append(f"{int(bad_amounts.sum())} row(s) have missing or non-numeric amounts (for example row {rows}). Enter a finite number such as 125.50; these records will be retained as invalid data.")
    bad_ids = bad_id & ~empty_rows
    if bool(bad_ids.any()):
        rows = ", ".join(str(int(i) + 2) for i in frame.index[bad_ids][:5])
        warnings.append(f"{int(bad_ids.sum())} row(s) have a blank transaction ID (for example row {rows}). Add an ID; these records will be retained as invalid data.")
    if duplicates:
        warnings.append(f"{len(duplicates)} duplicate transaction ID(s) found. Check whether each repeat is intentional; all related records will be flagged as duplicates.")
    if "description" not in frame:
        frame["description"] = ""
    frame["source_row"] = frame.index + 2
    frame["_invalid"] = invalid_mask
    return ValidationResult(frame, [], warnings, duplicates, invalid_rows)
