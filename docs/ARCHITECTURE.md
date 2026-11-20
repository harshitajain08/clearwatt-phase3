# ClearWatt 2.0 architecture and delivery boundaries

## Product surfaces

1. Consumer: bill upload, OCR review, audit, explanation, history and report.
2. Utility: controlled operational analytics and smart-meter ingestion. The current UI is a readiness preview; data access remains disabled pending RBAC and agreements.

## Service boundaries

- React/Vite frontend: presentation only; no secrets or tariff decisions.
- FastAPI: validation, orchestration, persistence, report generation and AI proxy.
- OCR adapter: PyMuPDF text extraction and Tesseract fallback.
- Audit engine: deterministic checks and explainable statistical screening.
- Tariff registry: versioned jurisdiction-specific rules. UPPCL FY 2026-27 is currently marked not_verified.
- Persistence: SQLAlchemy; SQLite local only, PostgreSQL for hosted environments.
- AI: OpenRouter called server-side; supplied audit record is the only evidence context; fallback remains useful.

## Trust boundaries and launch blockers

All bill records and uploaded files are sensitive. The current development API does not yet implement end-user authentication, ownership scoping, utility RBAC, encrypted object storage, signed links, retention controls or malware scanning. Therefore, it must not receive real consumer data in a public deployment. Those controls are mandatory before any pilot.

## UPPCL tariff validation protocol

1. Retrieve the signed FY 2026-27 UPERC state DISCOM tariff order and any later amendments/FPPAS notifications.
2. Transcribe each supported consumer schedule and record order page, table, effective date and source URL.
3. Independently verify the transcription against the signed order.
4. Build golden bill fixtures for rural/urban and category/load combinations.
5. Reconcile sample bills with UPPCL/DISCOM-approved calculations.
6. Enable the relevant tariff category only after approval; unsupported categories remain `not_verified`.

## Evaluation

The evaluation endpoint accepts a labelled test set and reports confusion matrix, accuracy, precision, recall, specificity, F1 and false-positive rate. Results are scoped to the supplied labelled dataset. No performance metric is published as a real-world claim until dataset provenance, sampling, leakage prevention and independent review are documented.
