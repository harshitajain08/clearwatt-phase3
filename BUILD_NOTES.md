# Build verification notes

- Backend: Python bytecode compilation passed.
- Backend tests: 13 passed (audit rules, meter-reading checks, evaluation metrics, change-point, K-Means, OCR field extraction, API health, manual audit, CSV ingestion and PDF report response).
- Database: initial Alembic migration successfully applied to a disposable SQLite test database; it creates the `audits` and `upload_drafts` tables without touching any existing database.
- API smoke checks: `/api/health`, `/api/audits`, and `/openapi.json` returned HTTP 200.
- Frontend: TypeScript syntax was inspected with the globally available compiler; full Vite production build could not be completed in this environment because package installation did not finish (network/package access timed out). Run `npm install && npm run build` in a normal Node environment before merging or deploying.
- UPPCL tariff: FY 2026-27 official order sources located, but the PDF extraction/transcription was not completed; tariff calculations remain explicitly disabled.
- No production Vercel deployment, production environment variables, database or user data were changed.

## Historical bill linkage update (local development)
- Audits now automatically assemble earlier saved bills from the local database when no explicit history is provided, chronologically sort by billing-period end, and retain up to 12 previous periods for analysis.
- The assembled history includes billing-period duration so daily-normalized comparisons can work.
- Audit history API now returns billing-period start/end, billed units and amount; the UI displays the bill period instead of only the audit creation date.
- Added regression test for saved-bill history linkage; backend test suite passes (14 tests).
- IMPORTANT: this is still a development-only shared local history. There is no account/meter isolation. Do not use real multi-user/consumer data or deploy publicly until identity and access scoping are implemented.
- Multi-file upload with one combined review/confirmation workflow is not implemented in this tranche; users can upload bills individually, and each later bill is compared against previously saved bills.

## Database + All Audits + report update
- Added `bills` table for persistent bill-period records and expanded audit snapshots with bill/customer/meter/DISCOM metadata.
- Historical bill comparison is scoped to matching `meter_ref`; anonymous records do not borrow another meter's history.
- Added `/api/audits/summary` and searchable/filtered `/api/audits` listing.
- All Audits UI now shows bill identifiers, meter/customer/provider metadata, units, amount and finding summaries.
- Expanded downloadable report to include bill calculations, historical comparison, algorithm interpretations, action steps, charge breakdown limitations and cautions.
- Added additive Alembic migration 0002 and tests for metadata persistence and meter-history isolation.
- Development only: no authentication/tenant-level access controls. Do not expose All Audits to a DISCOM or use identifiable customer data.
- Backend test suite: 23 passing in the build environment. Frontend dependency installation timed out; production frontend build remains unverified.
