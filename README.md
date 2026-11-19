# LedgerLens

LedgerLens is a local-first financial reconciliation workspace for comparing company ledger and bank statement CSVs. It validates source files, preserves every input row, classifies matches and exceptions, stores reconciliation runs, supports documented manual resolutions, and exports run reports.

All bundled example data is synthetic.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The default database is `sqlite:///ledgerlens.db`. To use SQL Server, install the Microsoft ODBC Driver and configure `DATABASE_URL`, for example:

```powershell
$env:DATABASE_URL = "mssql+pyodbc://user:password@server/database?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
streamlit run app.py
```

The SQLAlchemy models and repository are database agnostic; schema creation runs on startup. For production, apply migrations and use managed credentials rather than environment literals.

## CSV format

Both inputs require `transaction_id`, `date`, and `amount`. Optional `description` is retained. Dates are parsed with pandas; amounts must be finite numbers. Duplicate IDs and invalid rows are reported instead of discarded. Amount matching uses a one-cent tolerance. Matching is by transaction ID; when duplicate IDs exist in either source, every involved row is flagged as a duplicate exception and is not silently paired.

## Project structure

```text
ledgerlens/
  database.py       SQLAlchemy models and repository operations
  validation.py     CSV parsing and validation
  reconciliation.py deterministic matching/classification engine
  service.py        orchestration and persistence
  sample_data.py    reproducible synthetic data generator
  onboarding.py     first-run state helper
  components.py     shared workflow and validation components
  ui.py             centralized theme styling
  pages/            overview, upload, exception, and history renderers
app.py              Streamlit entry point and navigation
tests/               pytest coverage for core logic
data/                 bundled synthetic CSVs (500+ rows each)
.streamlit/config.toml finance-oriented Streamlit theme
```

## Workflows

- **Overview:** live metrics and recent runs are calculated from persisted results.
- **Upload & Reconcile:** upload separate files, review validation findings and previews, then persist a reconciliation.
- **Exceptions:** search/filter issues, inspect source rows side by side, and resolve with an auditable note.
- **History:** reopen past results and export a CSV report.
- **First run:** a guided welcome page offers a brief walkthrough and a small synthetic reconciliation. The small sample demonstrates every current matching status and is saved as a normal run.
- **Templates:** download header-only ledger and bank CSV templates from the upload page. Fill in transaction IDs, dates in an unambiguous format such as `YYYY-MM-DD`, and finite numeric amounts.

## Streamlit session state

The UI uses session state only for temporary workflow state; uploaded files are not persisted until reconciliation is submitted.

- `ledger`, `bank`: Streamlit upload widget values.
- `navigation_page`: selected sidebar route; `page` is mirrored in the URL query string.
- `latest_run`: last run ID opened or created in this browser session.
- `onboarding_dismissed`, `onboarding_force_open`: control first-run welcome and Help re-entry.
- `upload_files_present`, `upload_validation_passed`: current upload workflow progress.
- `exported_run_id`: tracks the run whose report was downloaded in this session.
- `exception_run`, `exception_choice_*`, filter keys: current exception selection and filters.

First-run detection checks whether the configured database contains any reconciliation runs. Dismissal is session-local; the Help section can reopen the welcome guide.

The existing database stores a single current resolution note per exception. The UI stores the selected disposition with that note; it does not provide prior-resolution history. Retaining every prior edit would require a separate append-only resolution history table and corresponding migrations.

Run the unit suite with `pytest`.
