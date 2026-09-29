# ADR 004 — Idempotent export ledger

Status: accepted.

Exports are keyed by workspace, document, approved version, schema version, and format. Repeated requests return the existing artifact after validating that approval is still current. A unique database key protects against concurrent claims, and the written artifact is stored under a scoped server-generated path. CSV and spreadsheet string cells are escaped against formula interpretation.
