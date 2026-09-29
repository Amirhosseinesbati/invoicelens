# InvoiceLens — independent portfolio project

## Case study

Harbor Industrial is a fictional B2B equipment distributor used to demonstrate a document operations workbench. An operator can upload invoices, purchase orders, and credit notes; compare extracted values with source evidence; resolve discrepancies; approve a versioned record; and download CSV, XLSX, or JSON. The product is a self-hostable commercial pilot starting point, not a deployed customer system or an audit-certified product. The data, vendors, transactions, and model responses in DEMO are synthetic.

I designed the workflow around reviewable evidence rather than an opaque extraction score. A source preview and structured record share page references, field boxes where the source allows them, and a correction trail. Arithmetic and PO comparisons are deterministic server rules. Approval binds to the exact extraction version and content hash; a correction invalidates the prior approval. A durable job and graph state handle long processing and human review. The React workbench uses an ivory/charcoal editorial system with cobalt selection, amber discrepancies, and green approved states.

The implementation uses FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL for a connected installation, LangChain structured model output, LangGraph checkpoints/interrupts, and a React/TypeScript/Vite/Tailwind client. DEMO runs against local SQLite with a deterministic adapter; CONNECTED has a configurable live model adapter. It exports accounting-ready files directly, without claiming an accounting API integration. Technical choices and limits are in [architecture](ARCHITECTURE.md) and [dependencies](DEPENDENCIES.md).

The fixed-seed synthetic benchmark contains 300 rendered source files: 220 invoices, 60 purchase orders, and 20 credit notes from 20 fictional vendors and 12 layouts, including 90 rasterized scans and 75 labeled discrepancies. A sequential Windows DEMO run with Tesseract 5.5.3 completed all 300 jobs. On held-out invoices, combined core-field exact match was 218/220 (99.1%) and line-field micro F1 was 96.2% (1,526 true positives; 1,614 expected; 1,557 predicted). Native and scanned core match were 100.0% and 97.1%, respectively. Finding recall was 70/75 (93.3%); strict precision was 70/122 (57.4%) because OCR errors and necessary review warnings produced 52 nonmatching document/kind pairs. See the [final OCR measurement](../evals/results/ocr-final-2026-09-28.md), [first complete OCR baseline](../evals/results/ocr-windows-baseline-2026-09-28.md), and [pre-repair OCR baseline](../evals/results/ocr-baseline-2026-09-28.md). The finding-precision release target remains unmet. Synthetic results do not establish customer accuracy or savings.

## Real product screenshots

The following PNGs were captured from the running React client and API with synthetic DEMO records on 2026-09-28. They are application states, not mockups. The measured browser journey reached login, overview, queue, source review, findings, batch upload, an unsupported-file rejection, version approval, and XLSX download. A correction pass created version 2 and an arithmetic finding, corrected it in version 3, reapproved, and downloaded a 6,110-byte XLSX. A later match-review pass rejected PO proposals, selected a PO, mapped an invoice line, approved version 5, and downloaded a 5,432-byte XLSX; both workbooks had valid ZIP headers. Full verification status is in [handover](HANDOVER.md).

| View | Width | Capture |
|---|---:|---|
| Overview and workload | 1440 px | [01-overview-1440.png](screenshots/01-overview-1440.png) |
| Source and evidence panel | 1440 px | [03-source-evidence-1440.png](screenshots/03-source-evidence-1440.png) |
| Actionable finding | 1440 px | [04-findings-1440.png](screenshots/04-findings-1440.png) |
| Batch intake | 1024 px | [05-batch-intake-1024.png](screenshots/05-batch-intake-1024.png) |
| Rejected invalid upload | 1024 px | [06-damaged-upload-1024.png](screenshots/06-damaged-upload-1024.png) |
| PO proposal resolution | 1440 px | [10-po-resolution-1440.png](screenshots/10-po-resolution-1440.png) |
| Mobile line mapping | 390 px | [11-line-mapping-mobile-390.png](screenshots/11-line-mapping-mobile-390.png) |
| Approved record and export actions | 1440 px | [09-approved-export-1440.png](screenshots/09-approved-export-1440.png) |

## 60–90 second demo script

1. **0:00–0:12 — Intake.** Open the synthetic DEMO. Upload a batch with native and scanned examples. Point out per-file acceptance, deduplication, and queued progress.
2. **0:12–0:28 — Review.** Open the exception queue, then an invoice. Select its total or line price and show the page/box evidence beside normalized values.
3. **0:28–0:48 — Resolve.** Show a PO comparison and arithmetic breakdown. Correct a source-reading error, explain that the edit creates a new version, and accept or reject a finding with a note.
4. **0:48–1:05 — Approve/export.** Approve the current version and download XLSX. Open the workbook and point out schema version, line rows, and escaped text cells.
5. **1:05–1:20 — Limits.** Show the damaged-upload state and explain the local Tesseract or configured live vision model requirement. State that the benchmark is synthetic and finding precision remains below its release target.

The script describes the implemented flow. The current synthetic accuracy targets and CONNECTED deployment checks remain open as documented in [handover](HANDOVER.md).

## 3–5 minute technical walkthrough

1. **0:00–0:40 — Scope and trust boundary.** Explain the single-customer installation, workspace-scoped records/files, authenticated roles, and separate DEMO/CONNECTED modes.
2. **0:40–1:25 — Pipeline.** Trace upload validation, durable job claim, page text/OCR, classification, typed extraction, normalization, deterministic validation and PO matching, then findings. Show the graph and state references in [architecture](ARCHITECTURE.md).
3. **1:25–2:10 — Evidence and correction.** Inspect a page box and raw/normalized value. Change one field, show a new extraction version and audit decision, and demonstrate that previous approval no longer authorizes export.
4. **2:10–2:50 — Reliability and export.** Describe job lease recovery, cancellation/retry, approval hash check, export ledger uniqueness, CSV formula escaping, and the exact active-version guard.
5. **2:50–3:45 — Evaluation.** Explain the generated scenario truth, held-out vendor/layout split, per-field denominators, native/scanned separation, false positives, and why strict finding precision misses its 90% target.
6. **3:45–4:30 — Deployment path.** Show lockfiles, migrations, Compose, backup/restore requirements, CONNECTED credentials and budget, OCR requirement, and the remaining live checks.

## Content angles

- **Evidence-first UX:** Why field-level source links and visible before/after edits make document AI review more accountable than a single confidence badge.
- **Workflow reliability:** How version-bound human approval, durable jobs, and idempotent export claims handle retries without treating a graph checkpoint as a job queue.
- **Honest synthetic evaluation:** How separate scenario truth, held-out layouts, and explicit failed scans prevent a polished demo from becoming an unsupported accuracy claim.

## Resume bullet templates using measured facts

- Built an independent FastAPI/LangGraph and React invoice-review pilot with source-linked extraction, versioned correction/approval, workspace-scoped access, and CSV/XLSX/JSON exports.
- Generated a reproducible 300-document synthetic benchmark spanning 20 vendors, 12 layouts, 1,367 invoice lines, and 75 labeled discrepancies; kept evaluator truth separate from runtime inputs.
- Measured a sequential 300-job OCR-enabled DEMO run with 99.1% combined held-out core-field exact match and 96.2% line-field F1; documented 57.4% strict finding precision and 93.3% recall against planted synthetic cases.

Use these bullets only with the words **independent portfolio project** and **synthetic benchmark** nearby; they are not customer impact claims.
