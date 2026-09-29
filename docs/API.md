# API contract

The FastAPI OpenAPI schema at `/openapi.json` is the executable API description; `/docs` provides an interactive view. The React client sends same-origin `/api` requests through Vite's proxy in local DEMO and Caddy's reverse proxy in the Compose image. Auth uses an HttpOnly session cookie scoped to `/api`. All document IDs, job IDs, page URLs, and exports are checked against the authenticated user's workspace. Admins and operators can mutate; viewers can read.

## Authentication and status

| Method | Path | Purpose |
|---|---|
| `GET` | `/api/health` | Database-backed health and mode |
| `POST` | `/api/auth/login` | `{ "email": "...", "password": "..." }`; sets session cookie and returns `user` |
| `GET` | `/api/auth/me` | Current user, role, workspace |
| `POST` | `/api/auth/logout` | Clears session cookie |
| `GET` | `/api/settings` | Actual mode, model/OCR availability, workspace and export formats |

The deployment sets `INVOICELENS_ALLOWED_ORIGIN` and `INVOICELENS_COOKIE_SECURE`. The login token expires after 12 hours. A `401` means sign in or refresh the session; `403` means the role cannot perform the operation.

The web client's request/response types are checked against the generated OpenAPI document by `pnpm -C apps/web check:api`. CI exports the FastAPI schema without starting a worker and checks route methods plus typed response models and nested evidence/line/finding properties. A missing response model fails the contract check.

## Workload and ingestion

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/overview` | Scoped counts for documents, review, processing, findings, vendors, exports |
| `POST` | `/api/uploads` | Multipart `files` field repeated for up to 50 PDF/PNG/JPEG sources; per-item success, duplicate or actionable rejection |
| `GET` | `/api/jobs` | Scoped persisted jobs |
| `GET` | `/api/jobs/{job_id}` | Status, progress, page counts, failure reason |
| `GET` | `/api/jobs/{job_id}/events` | Server-sent events with observable type, message, progress and time |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a queued/processing job |
| `POST` | `/api/jobs/{job_id}/retry` | Requeue a failed/cancelled job |

An upload result is `{ "items": [{ "document_id": "...", "job_id": "...", "status": "queued", "deduplicated": false, "error": null }] }`. The batch can contain both successful and rejected items. A duplicate source in the same workspace returns the existing document/job reference. Job status is persisted, so a client can reload the page and continue polling or reconnect to events.

## Documents and review

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/documents` | Workspace-scoped summary list |
| `GET` | `/api/documents/{id}` | Current version, pages, fields/evidence, lines, findings, PO proposals, audit history, approval |
| `GET` | `/api/documents/{id}/versions` | Workspace-scoped extraction history with version, fields, lines and content hash |
| `GET` | `/api/documents/{id}/versions/{version}` | One historical extraction version for before/after inspection |
| `GET` | `/api/documents/{id}/source` | Protected original PDF/image |
| `GET` | `/api/documents/{id}/pages/{page}/image` | Protected PNG page preview |
| `POST` | `/api/documents/{id}/corrections` | Create a new version, audit before/after and recalculate findings |
| `POST` | `/api/documents/{id}/revalidate` | Re-run deterministic findings for the current version, including newly arrived POs |
| `POST` | `/api/documents/{id}/matches/decision` | Select a current scoped PO proposal or explicitly reject all; creates a new version |
| `POST` | `/api/documents/{id}/line-matches/decision` | Map an invoice line to a line on its selected PO; creates a new version |
| `POST` | `/api/documents/{id}/findings/{finding_id}/decisions` | Accept or reject a current-version finding |
| `POST` | `/api/documents/{id}/approve` | Approve exactly the requested current version |
| `GET` | `/api/documents/{id}/exports?format=csv|xlsx|json` | Download approved version; first request materializes an idempotent artifact |
| `GET` | `/api/vendors` | Vendor list and scoped invoice counts |

Correction body: `{ "field": "total", "value": "120.00", "reason": "Corrected OCR digit against page 1" }`. Line-item keys use `lines.<zero-based-index>.<sku|description|quantity|unit|unit_price|amount>`. A changed value creates a new version and clears the old approval; an identical retry is a no-op. Finding decision body: `{ "decision": "accepted", "note": "Reviewed source" }` or `rejected`.

PO match decision body: `{ "version": 2, "decision": "selected", "po_id": "<matches[].po_id>", "note": "Verified PO" }`; use `decision: "rejected"` with `po_id: null` to record that no proposal was accepted. Line match body: `{ "version": 3, "invoice_line_index": 0, "po_line_id": "<candidate.po_line_id>", "note": "Verified line" }`. Both return `DocumentDetail` with an incremented version and invalidate prior approval. A repeated identical decision on the current version is idempotent. Detail exposes `match_resolution`, `matches[].status`, `line_matches`, and `line_match_candidates` even after ambiguity has been resolved. `AMBIGUOUS_LINE_MATCH.details` also lists affected invoice indices and candidate PO line IDs.

Approval body: `{ "version": 4 }`. A stale version, unknown document kind, open error, ambiguous vendor/PO/line match, stale PO choice, unconfirmed fuzzy proposal, unreadable matched PO row, or cumulative approved invoice quantity above a PO line's ordered quantity returns `409`. Concurrent approvals claiming the same PO line are serialized. A correction to a matched PO revalidates dependent invoices and revokes their old approvals in the same transaction. Accepting an ambiguity finding alone does not bypass the required match choice. A missing PO is shown as `PO_NOT_FOUND`; it does not claim that a similar numbered PO is the right one. Vendor aliases with multiple known full-name candidates require a vendor field correction before approval. `PO_LINE_SOURCE_UNVERIFIED` and `ARITHMETIC_UNVERIFIED` distinguish uncertain source readings from confirmed business discrepancies.

Each field in document detail carries `raw`, normalized `value`, `page_number`, `span_start`, `span_end`, optional `bbox`, and `source`. Bounding boxes use page coordinates relative to the returned page width/height. A missing span or box is `null`, not a generated location. The page preview and field evidence are both protected by workspace auth.

JSON exports carry `schema_version: "1.0"`, `document_id`, `document_version`, `kind`, normalized header fields, and line items. CSV/XLSX flatten one row per line item with the same schema version and header values repeated. Unsupported formats return `422`; unapproved or changed versions return `409`. An export request never posts to an external accounting service.
