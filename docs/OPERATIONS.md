# Operations

## Local DEMO

From the repository root, run `pwsh -File scripts/demo.ps1 -Size fast` on Windows or `bash scripts/demo.sh fast` on POSIX. The scripts install the locked API/web dependencies, generate the synthetic source fixture if needed, migrate, seed four prerequisite purchase orders, and start the API and client. The five PDFs named `INV-*.pdf` in `generated/invoicelens-fast/documents` remain available for a fresh batch upload. Use `-Size full` or `full` for the 300-document dataset. Use `-PrepareOnly` / `--prepare-only` to seed without starting servers. `-Reset` / `--reset` is an explicit DEMO-only namespace reset; ordinary starts preserve existing records. Stop the foreground command with Ctrl+C.

The default UI is `http://127.0.0.1:5789`, API health is `http://127.0.0.1:8790/api/health`, and OpenAPI is at `http://127.0.0.1:8790/docs`. The API log in direct-run DEMO is `data/api.stderr.log`. Native PDFs require no OCR service; scanned pages need a local Tesseract executable or a configured vision model in CONNECTED mode. The Windows launcher recognizes a private `tmp/tesseract-ocr` copy when present and caps Tesseract at one CPU thread. The generator uses Poppler `pdftoppm` for image-only synthetic PDFs.

## Connected customer installation

1. Copy `.env.example` to `.env`. Set a long unique URL-safe `POSTGRES_PASSWORD` and an `INVOICELENS_SECRET_KEY` of at least 32 characters, plus `INVOICELENS_OPENAI_MODEL` and `INVOICELENS_OPENAI_API_KEY` with an agreed spending cap. `INVOICELENS_OPENAI_MAX_OUTPUT_TOKENS` defaults to 2048 and must be 256–8192. The password is inserted into a SQLAlchemy URL by Compose. Set `INVOICELENS_MODE=CONNECTED`; do not import the synthetic manifest.
2. Run `docker compose config -q`, then `docker compose up --build -d`. The API image applies Alembic migrations before serving. The checkpoint schema initializes idempotently on its first graph operation. Inspect `docker compose ps`, `docker compose logs api`, and `/api/health`.
3. Create the customer's first workspace and admin interactively (replace all example values):

   ```bash
   docker compose exec api python -m invoicelens.bootstrap --workspace customer-slug --name "Customer Name" --email admin@example.com
   ```

   The command prompts for a password of at least 12 characters. Do not put the password in shell history, docs, or environment files. Each commercial installation is intended for one customer; workspaces are still scoped at every record boundary.
4. Put the UI behind HTTPS, set `INVOICELENS_COOKIE_SECURE=true`, configure the public `INVOICELENS_ALLOWED_ORIGIN`, restrict database and API access, and verify a login, native upload, review, approval, and downloadable export with permitted customer test data.

The only required outbound connector is the configured model provider. The CSV/XLSX/JSON download is the accounting integration for v1. There is no accounting API posting. A provider error remains visible and never becomes a simulated successful response in CONNECTED mode. Configure provider ID and credentials per customer, with a bounded budget and no source-content tracing by default. CONNECTED job events record input/output token counts when returned, prompt version, and `cost_status=unknown`; they do not infer a monetary cost without an explicit pricing source.

## Backup and restore rehearsal

Back up both the PostgreSQL database (business data and graph checkpoints) and the `storage_data` volume (sources, page previews, exports). Encrypt and restrict both backups. A database dump without matching files cannot restore evidence or downloads.

Example PostgreSQL dump inside the database container:

```bash
docker compose exec db pg_dump -U invoicelens -Fc -f /tmp/invoicelens.dump invoicelens
docker cp "$(docker compose ps -q db):/tmp/invoicelens.dump" ./invoicelens.dump
```

On PowerShell, obtain the container ID first with `$dbContainer = docker compose ps -q db`, then use `docker cp "${dbContainer}:/tmp/invoicelens.dump" .\invoicelens.dump`. Back up the storage volume with the deployment's approved volume/snapshot tool at the same recovery point. Record database schema revision and application image versions with each backup.

For a restore smoke test, create a **separate** PostgreSQL database or isolated installation, copy the dump into that container, run `pg_restore -U invoicelens -d <restore-test-db> /tmp/invoicelens.dump`, restore the paired storage snapshot, and check document counts, one protected source preview, one approved export, and one paused/recovered job. Do not run a restore test over a live customer database. An isolated local PostgreSQL dump/restore recovered the Alembic revision and four checkpoint tables, and the disposable restore database was removed. The paired storage-volume and document-level restore rehearsal remains pending.

## Jobs, retries, and retention

Upload jobs persist status, page progress, failure reason, attempts, and a lease. The worker reclaims expired leases after restart. Operators can cancel or retry through the workbench/API; a retry should preserve previously committed document versions and decisions. Review job events before repeated retries of a damaged or encrypted file. Bound model timeouts and budgets in customer configuration.

For an ambiguous vendor, correct the vendor field to the verified full name. For an ambiguous or fuzzy PO proposal, select the verified PO or explicitly reject all proposals. If a selected PO has several prices for one SKU, map each affected invoice line to a PO line. These actions are audited and create a new version, so use the returned version for approval. Approval stays blocked while these choices remain unresolved. If an exact PO is unavailable because its source is still queued or failed OCR, inspect that job and retry it; the application does not silently substitute a neighboring PO number.

Agree on a document and export retention window with each customer. Backup retention and logs must match that policy. The pilot does not provide a public self-service retention portal; use the dry-run-first, workspace-scoped [retention maintenance procedure](RETENTION.md) and verify scope before deletion. Redact source content, personal data, and credentials from logs and optional traces; disable provider tracing unless explicitly configured and approved for the customer's data policy.
