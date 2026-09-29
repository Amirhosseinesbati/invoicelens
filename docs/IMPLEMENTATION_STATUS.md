# InvoiceLens implementation status

Updated: 2026-09-28. The self-hosted pilot and local DEMO workflow are implemented. The synthetic finding-precision release target remains incomplete; targets are never inferred from passing tests.

## Implemented

- FastAPI/Pydantic/SQLAlchemy/Alembic API with workspace-scoped users, source files, pages, durable jobs, extraction versions, evidence, findings, decisions, approvals, and idempotent CSV/XLSX/JSON exports.
- LangGraph workflow with recoverable job scheduling, LangChain structured CONNECTED adapter, bounded page batches, and deterministic offline DEMO adapter. No live provider success is simulated on failure.
- React/TypeScript workbench with upload, progress, review queue, resizable source/evidence view, corrections, PO/line match decisions, version-bound approval, and downloads.
- Fixed-seed 300-source synthetic corpus (220 invoices, 60 POs, 20 credit notes), 20 vendors, 12 layouts, 1,367 invoice lines, 90 scans, and 75 planted findings. Private truth stays outside runtime input.
- One-command Windows/POSIX DEMO launch, pinned dependency lockfiles and container tags, migrations, Compose deployment, CI gates, retention maintenance, API/product/operations/security documentation, and portfolio screenshots.

## Verified on this host

- Final integrated backend/evaluator/generator/exporter suite: **55 passed**. Ruff check and format on `apps/api/src` and `tests/backend`, plus full-package `ty check`, passed. The latest frontend lint, TypeScript typecheck, and production Vite build passed (1,567 modules). Offline OpenAPI contract check passed 22 required routes and 26 typed schemas.
- The fast Windows DEMO command started the API and web client, seeded four prerequisite POs, returned API health `200` in `DEMO` mode and web HTTP `200`, and stopped cleanly. The local launcher uses a project-private Tesseract copy when present and limits OCR to one thread.
- Real Chrome browser journeys covered login, batch upload/rejection, protected source and evidence, correction to v3, finding review, explicit PO/line selection to v5, approval, and valid XLSX downloads. Screenshots cover 1440, 1024, and 390 px in `docs/screenshots`; mobile overflow was corrected and rechecked.
- Backend integration tests cover cross-workspace access, retry/cancel, evidence, version history, correction idempotency, unknown-kind block, export/approval concurrency, cumulative PO-line claims across invoices, and invalidation of dependent approvals after PO correction. A two-thread approval race yielded one approval and one `409` when both invoices would exceed the PO quantity.
- Before the last backend rule changes, local Compose API/web images built, PostgreSQL/API health and web proxy returned `200`, Alembic reported `0001_initial (head)`, and an isolated PostgreSQL dump/restore recovered the migration and four checkpoint tables. The paired source-volume restore remains pending.
- Final offline DEMO evaluation at the last code revision processed **300/300 documents**, including 90 scans, using project-local Tesseract 5.5.3 with one OCR thread. Held-out combined core exact match was **218/220 (99.1%)** and line-field micro F1 was **96.2%** (1,526 TP; 1,614 expected; 1,557 predicted). Native/scanned core results were 150/150 (100.0%) and 68/70 (97.1%). Finding precision was **70/122 (57.4%)** and recall **70/75 (93.3%)**, with 52 false-positive and five false-negative pairs. Complete artifacts are `evals/results/ocr-final-2026-09-28.{json,md}` and its prediction archive; earlier baselines remain preserved.

## Release and deployment limits

- Extraction and finding recall passed their synthetic targets; strict finding precision did **not** reach 90%. OCR sign/SKU/amount errors and legitimate source-quality or manual-selection warnings account for many false positives. The quality release gate stays incomplete; no real-customer accuracy or savings claim is made.
- CONNECTED adapter contract is implemented and tested without live credentials. A live model smoke needs configured credentials and an agreed provider spending cap. Customer HTTPS/cookie configuration, layout evaluation, and paired database-plus-file restore still need customer-specific verification.
- Mixed-vendor ambiguous numeric/date strings depend on installation-wide locale settings; a vendor-specific locale policy is pending. Logout clears the cookie but cannot revoke a copied signed token before its 12-hour expiry. A server-side session ledger is needed if immediate revocation is required.
- Docker on this host later reported an image-store I/O error during evaluation, so the final OCR measurement used Windows Tesseract instead of rebuilding the latest container image. No unrelated Docker containers were changed. The first interrupted container evaluation and a later 240/300 partial batch are not scored. A stale local installer cache was moved reversibly to ignored `tmp/c-drive-recovery` to restore C: space; it is not a project dependency.

The exact final source revision is identified in [HANDOVER.md](HANDOVER.md). [EVALUATION.md](EVALUATION.md) defines every metric, split, and baseline.

