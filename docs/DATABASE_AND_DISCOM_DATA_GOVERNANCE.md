# ClearWatt bill storage and DISCOM data architecture

## What is stored

Each completed analysis creates an immutable audit snapshot in `audits` (result JSON, source payload, analysis status, optional customer/meter/provider references, dates, units, amount, and bill link). Bill-period data is separately stored in `bills`, so a bill can be retained as a distinct record and an audit can be re-run without overwriting the earlier result snapshot.

## History linking

Historical comparison is now scoped to a matching `meter_ref`. Anonymous uploads/manual entries are saved but do not borrow history from other meters. For synthetic testing, enter the same stable meter reference on all bills for one fictional connection, e.g. `CW-SYNTH-001`. Use a different reference for a different household. A bill with the same meter reference and exact period start/end updates the bill-period record; each reanalysis still creates a new audit record.

## All Audits

The All Audits page shows locally saved audit runs, bill/meter/provider metadata, units, amount, finding count and finding titles. Search matches audit ID, customer reference, meter reference, provider, period, summary and finding title. The API also supports optional `search`, `status`, `discom` and `meter_ref` query parameters and provides `/api/audits/summary`.

## Multi-customer / DISCOM readiness is not production access

This development build does not implement authentication, account verification, roles, DISCOM tenant boundaries, consent management, retention enforcement, or row-level access policies. All local All Audits records are visible to the local workspace. Do not put identifiable customer data in this build or expose it publicly. The references are metadata fields only; they are not proof of a verified customer identity or meter ownership.

Before a DISCOM pilot, implement and test: authentication, verified consumer/meter identity, consumer-to-connection ownership, DISCOM tenant isolation, least-privilege roles, access logs, consent and purpose limitation, retention/deletion policy, secure bill file storage, and database row-level policies. DISCOM analytics should use appropriately aggregated/de-identified data by default, and record-level access should require a defined operational role and legitimate workflow.
