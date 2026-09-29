# InvoiceLens handover

Date: 2026-09-28. InvoiceLens is an independent portfolio project and a customer-installable pilot starting point. All bundled DEMO documents and accounts are synthetic. It has not been deployed to a customer or certified for accounting/audit use.

## Source revision

The final local Git revision is identified by tag `invoicelens-pilot-2026-09-28`. In this checkout, run `git rev-parse invoicelens-pilot-2026-09-28` to obtain the exact commit SHA. The tag is assigned only after the final checks and documentation are committed; if it is absent, the handover is still in progress. The local product requirements are retained outside the public source snapshot.

## Start the local DEMO

Prerequisites: Python 3.12, uv, Node.js 24, pnpm 11, and Poppler `pdftoppm` to generate the scanned synthetic files. Tesseract with the `eng` model is required to read image-only sources locally. This host's private portable copy is in ignored `tmp/tesseract-ocr`; the Windows launcher finds it automatically when no system `tesseract` command exists and limits OCR to one thread. Ports 8790 and 5789 must be available.

Windows PowerShell, from any shell:

```powershell
Set-Location '/path/to/invoicelens'
# Set INVOICELENS_PYTHON to a Python 3.12 executable only if uv cannot discover one.
pwsh -NoProfile -File scripts/demo.ps1 -Size fast
```

POSIX shell:

```bash
cd /path/to/invoicelens
bash scripts/demo.sh fast
```

Open `http://127.0.0.1:5789`; API health is `http://127.0.0.1:8790/api/health`. These commands install locked dependencies, generate the fast fixture if needed, apply the migration, seed two DEMO workspaces and four prerequisite purchase orders, and start both services. Upload the five `INV-*.pdf` files in `generated/invoicelens-fast/documents` as a fresh batch. `-PrepareOnly` / `--prepare-only` stops after setup. `-Size full` / `full` creates the 300-document corpus. `-Reset` / `--reset` explicitly replaces DEMO workspace records only; it is useful to reseed after parser changes. Stop the foreground command with Ctrl+C.

| Login | Password | Role | Workspace |
|---|---|---|---|
| `admin@example.com` | `DemoPass123!` | admin | harbor-demo-a |
| `operator@example.com` | `DemoPass123!` | operator | harbor-demo-a |
| `viewer@example.com` | `DemoPass123!` | viewer | harbor-demo-a |
| `operator2@example.com` | `DemoPass123!` | operator | harbor-demo-b |

Use these credentials only with the synthetic DEMO. They are never seeded in CONNECTED mode.

## Verification matrix

| Area | Implemented | Checked on this host | Remaining release work |
|---|---|---|---|
| File intake, validation, deduplication, persisted jobs | Yes | Backend integration and browser upload/rejection | Live deployment load/restart rehearsal |
| Native PDF extraction, source evidence, line items | Yes | Native rendered samples and browser source panel | Customer layout calibration |
| Scanned PDF/image OCR | Tesseract adapter and API container install | Final local OCR run: 300/300 jobs complete, scanned held-out core match 68/70 (97.1%), scanned line F1 95.0% | Customer layout calibration and human-reviewed samples |
| LangGraph review, correction, findings, versioned approval | Yes | Browser correction to v3/reapproval; backend approval race, cumulative PO claim, unknown-kind, and PO-correction invalidation tests | PostgreSQL checkpoint recovery rehearsal |
| CSV, XLSX, JSON download | Yes | Backend export tests and browser XLSX downloads for v1 and corrected v3 (6,110-byte workbook with ZIP header) | Verify output mapping with a customer's accounting import |
| Workspace roles and file scope | Yes | Cross-workspace/API integration tests | Customer access review and deployment configuration |
| React responsive workbench | Yes | 1440/1024/390 Chrome screenshots, overflow repaired | Final keyboard/assistive-technology review |
| CONNECTED model adapter | Yes | Configuration/schema contract only | Credentialed live smoke under agreed spending cap |
| Compose/PostgreSQL deployment | Yes | Both images built; Compose PostgreSQL/API healthy, web and API proxy HTTP 200, Alembic `0001_initial (head)`, PostgreSQL graph checkpoint compiled; isolated `pg_dump`/`pg_restore` recovered the migration and four checkpoint tables | Paired file-volume restore and customer HTTPS configuration |
| Synthetic benchmark and evaluator | Yes | Complete 300-job Windows OCR run, native/scanned split, evaluator tests | Finding-precision release target |

The [implementation status](IMPLEMENTATION_STATUS.md) records the latest checks. The [evaluation report](EVALUATION.md) explains denominators, splits, and release targets. The final local OCR result is preserved in `evals/results/ocr-final-2026-09-28.{json,md}`, with its actual prediction archive. All 300 jobs completed. Held-out combined core exact match was 218/220 (99.1%) and combined line-field F1 was 96.2%; findings had 70/122 strict precision (57.4%) and 70/75 recall (93.3%). Extraction and recall passed their targets, while finding precision did not; the quality release gate remains incomplete. These synthetic figures do not estimate real-customer accuracy. Earlier no-OCR and pre-repair OCR measurements remain archived for comparison.

## Connected customer installation

Copy `.env.example` to `.env`, set unique PostgreSQL and application secrets (the latter at least 32 characters), model ID/API key, a provider spending cap, locale/currency policy, and HTTPS origin. Run `docker compose config -q` and `docker compose up --build -d`. Then create the first customer workspace/admin using `docker compose exec api python -m invoicelens.bootstrap --workspace customer-slug --name "Customer Name" --email admin@example.com`; this command prompts for a password. No real credentials belong in this repository.

Before customer use, run a native and scanned document smoke, compare evidence and accounting output with an operator, configure retention and backup, perform an isolated restore, verify workspace roles, and review exact image/package licenses. Configure a vendor-specific locale policy before accepting ambiguous dates or amounts in mixed-locale customer data; the current global `date_order`/`decimal_separator` configuration does not resolve every value such as `1,234` in a three-decimal currency. Set `INVOICELENS_COOKIE_SECURE=true` behind HTTPS. An external accounting posting connector is outside v1; the supported integration is download of approved CSV/XLSX/JSON. Full steps are in [operations](OPERATIONS.md), [security](SECURITY.md), and [commercialization](COMMERCIALIZATION.md).

## Test-environment note

The managed execution sandbox on this host could read the local SQLite graph checkpoint but was denied writes despite workspace ACLs. Its first browser approval returned a 500. Restarting the synthetic API with approved write access to this project's SQLite files made the same approval request succeed. The managed shell also needed approved access to Docker's socket. These were test-process permissions, not required settings for a normal user shell. Both images and a local Compose health/proxy smoke completed before the last backend changes. An isolated PostgreSQL dump/restore recovered the application migration and checkpoint tables; a paired storage-volume restore and live model quality test remain pending. The Docker image store later returned an I/O error during evaluation, so the complete post-repair 300-job OCR result was measured with a project-local Windows engine.

