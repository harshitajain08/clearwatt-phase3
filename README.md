# ClearWatt 2.0

Consumer-first electricity bill auditing and utility intelligence. The November 16 ZIP is retained as the development baseline; the original vanilla prototype files are preserved as `prototype-*`. The active consumer UI is React + TypeScript and the API is FastAPI.

## Current implementation slice

- Responsive consumer-first bill upload and manual-entry experience.
- Upload validation for PDF/JPG/PNG/WEBP with size limit.
- OCR extraction via PyMuPDF and Tesseract, followed by an explicit human review step.
- Meter reading sequence and meter-delta reconciliation.
- Historical daily-normalised consumption screening using median and modified Z-score.
- Explainable Isolation Forest, K-Means, mean-shift and labelled evaluation primitives.
- PostgreSQL-ready SQLAlchemy persistence; SQLite is local development only.
- Server-side OpenRouter explanation with deterministic fallback.
- Downloadable PDF audit report.
- UPPCL FY 2026-27 tariff source registry, deliberately disabled pending line-by-line transcription and independent verification of the official signed rate schedule.
- Separate utility workspace preview; no utility access to consumer records is enabled until RBAC and data-sharing controls exist.

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

Tesseract OCR must also be installed on the host for image OCR and scanned-PDF OCR. For macOS: `brew install tesseract`.

### Frontend

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. API docs: `http://127.0.0.1:8000/docs`.

### Tests

```bash
cd backend
pytest -q
```

## Production requirements before any public launch

This code is a development implementation slice, not a production certification. Before deployment with real consumer bills, implement and test authentication, tenant/owner-level authorisation on every audit and file endpoint, malware scanning, encrypted object storage, signed upload/download URLs, retention and deletion workflows, Alembic-managed migrations, managed PostgreSQL backups, background workers, rate limiting, CSRF/session protections as applicable, secrets management, observability, incident response, and a security review. Do not deploy the SQLite development configuration as production.

## UPPCL tariff status

The official UPPCL tariff-details page and UPERC FY 2026-27 state-DISCOM tariff order have been located. The official UPPCL PDF is linked from the UPPCL tariff details page; the UPERC order is dated 02 July 2026. The actual category/rate schedule is **not enabled** in this build. The signed order must be transcribed and checked for each applicable DISCOM, category, rural/urban supply schedule, load, slab, fixed/demand charge, subsidy, rebate, FPPAS, electricity duty, minimum charge and effective date. Until then, ClearWatt explicitly returns `not_verified` and does not claim tariff correctness.

## Important interpretation rules

- A statistical anomaly is not a probability that a bill is wrong.
- Higher consumption and higher amount are different phenomena; this release screens consumption and meter readings only.
- No real-world accuracy, savings, fraud-detection or DISCOM impact claims may be made without representative labelled validation data and an approved pilot.
- The utility workspace is a preview, not an authenticated DISCOM portal.

## Docker Compose development stack

```bash
cp .env.example .env
# Change POSTGRES_PASSWORD in .env or export it before running.
docker compose up --build
```

Open `http://localhost:8080`. The Compose stack uses a separate `clearwatt2` PostgreSQL database and a named volume. It does not connect to the existing production ClearWatt database or deployment. The default Compose password is for local development only.

For production migrations, set `APP_ENV=production`, configure `DATABASE_URL`, then run `alembic upgrade head` from the project root before starting the API. Back up the target database and rehearse migrations on a staging clone first.

### Saved historical bills (development update)
When you complete bill checks individually, ClearWatt now automatically uses earlier saved bill records whose billing periods end before the current bill's start. It orders them by period and uses the latest available history (up to 12 periods) for daily-normalized comparisons. The history screen now shows the bill period and consumption/amount where available. Multi-file upload-and-review is planned separately. This feature is development-only because local records are not yet isolated by user or meter.

## ClearWatt 2.1 ML integration development update

The 2.1 development update integrates transparent algorithm run statuses into bill audits and smart-meter CSV analysis. The Utility workspace includes a deterministic synthetic benchmark with held-out metrics and confusion matrix. Read `docs/CLEARWATT_2_1_ML_INTEGRATION.md` for methodology, sample-size requirements, benchmark limitations, and local setup.


**Do not use synthetic benchmark scores as real-world accuracy claims.** This development build remains unauthenticated and is not safe for public deployment with real consumer data.

## 2.2 database-backed bill records and audit history

This update stores completed bill-period records separately from audit snapshots. Enter a stable, fictional or anonymised **Meter ID / connection reference** when testing a sequence of bills; only bills associated with that meter reference are used as historical context. Customer reference and DISCOM fields are optional metadata. Each completed analysis remains its own audit run, while a bill-period record can be updated for the same meter and exact billing period.

The **All Audits** page displays locally stored analysis records and supports search across audit ID, customer reference, meter reference, DISCOM, dates and finding titles. The API supports optional `search`, `status`, `discom` and `meter_ref` filters. `GET /api/audits/summary` returns local counts.

The PDF report now includes a bill-details table, calculated daily use and baseline indicators, plain-language finding interpretation, method descriptions, algorithm status/outputs, next steps, charge-analysis limitations and verification guidance.

**Important:** This remains a local development build. Authentication, verified identity, role permissions, tenant/row-level security, consumer consent and a secure DISCOM data-sharing workflow are not implemented. The All Audits page is not a secured DISCOM portal. Use synthetic or anonymised records only and do not expose it publicly.

Database migration: `backend/migrations/versions/0002_bill_records_and_audit_metadata.py`.
# clearwatt-phase3
