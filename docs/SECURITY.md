# Security model and deployment checks

InvoiceLens handles financial source documents. A pilot installation should be private to one customer and use HTTPS, PostgreSQL credentials, a unique application secret, restricted storage, and an agreed retention policy. The synthetic DEMO is separate from customer data and its example passwords must never be reused.

## Application boundaries

- The server authenticates users and checks admin, operator, or viewer role together with workspace on every document, page, job, event, finding, correction, approval, and export route. A graph thread or file ID alone grants no access.
- The server creates storage paths from scoped IDs. Uploaded filenames are display metadata only and cannot select a filesystem path. Uploads are checked by size, signature, type, and PDF/image integrity before processing; source pages also have a raster pixel/side limit before OCR or model image rendering.
- Extraction output, OCR text, source documents, and model responses are untrusted content. They cannot override prompts, authorization, workflow policy, or export eligibility.
- Approval binds to the current data version and hash. Field corrections, PO choices, and line mappings create a new version and invalidate the earlier approval. The server checks that a chosen PO is a current proposal in the user's workspace and that a chosen PO line belongs to that PO and has the same SKU. Unresolved vendor/PO/line ambiguity blocks approval even if a generic finding decision was recorded; export rechecks the current approval.
- CSV and XLSX string cells must be escaped if they could be interpreted as formulas. JSON export carries a schema version. Secrets stay in server configuration and are omitted from logs and exports.
- CORS should admit only the configured client origin. Deployment cookies require `Secure`, `HttpOnly`, and `SameSite` behavior appropriate to the HTTPS topology.

## Deployment checklist

1. Replace the DEMO secret and users. Create an isolated customer database/installation and an administrator with a strong password.
2. Terminate HTTPS at a trusted reverse proxy and set `INVOICELENS_COOKIE_SECURE=true`. Restrict service ports and database access to the intended networks.
3. Set upload limits, file permissions, backup encryption, log retention, and deletion policy for documents and exports.
4. Configure model/OCR credentials and provider data-handling agreements. Do not enable source-content tracing by default.
5. Run workspace-boundary, malformed upload, formula-injection, approval-version, and retry/concurrency tests in the deployment environment.

## Known verification boundary

Sessions use signed, expiring tokens in an HttpOnly cookie. Logout clears the browser cookie; a copied token is not revoked server-side before its 12-hour expiry. Customer deployments needing immediate session revocation require a server-side session ledger. Numeric/date parsing currently uses installation-wide locale settings; mixed-vendor ambiguous values require a vendor policy and operator review before relying on an export. The CONNECTED adapter has bounded page batches and per-call output limits, while an enforceable provider monetary cap must be configured outside this application before customer use.

This document describes the controls expected of the pilot. [HANDOVER.md](HANDOVER.md) and [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) record which have actually been exercised. No audit certification or compliance attestation is claimed.
