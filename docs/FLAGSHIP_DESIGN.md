# InvoiceLens flagship review workbench

Implemented locally on 2026-10-06. This document preserves that calibration's decisions and evidence. The subsequently selected [production Command workspace and themes](COMMAND_THEMES.md) now supersede these shell/review visuals and calibrate all seven workflows. All illustrated documents and vendors are synthetic; no live extraction-quality claim is made.

## Design decisions

- A quiet 208 px navigation rail and 52 px location header keep the invoice in focus. Vendor, document number, server version, review status and stated amount establish the working context. The source occupies 54% of the resizable desktop workbench.
- A compact 44 px source toolbar consolidates filename, paging, zoom and download. The actual rendered PDF fits the available viewport through a cleaned-up ResizeObserver. Zoom remains relative to that fit; it does not alter evidence coordinates.
- Details, Findings and Activity share one controlled tab state. Identity fields, an operational line-item table and reconciliation replace a long undifferentiated field list. Selecting a value highlights only coordinates supplied by extraction, and the evidence dock names the field, page and current value.
- The synthetic invoice's real UNIT_PRICE_MISMATCH finding links to the affected line's unit-price evidence. The attention strip and disabled approval reason use actual open findings. Approval and export remain server-confirmed and version-bound.
- Below 1000 px, Details and Document become separate tasks with a persistent action bar. Below 600 px, reader mode compresses the vendor/amount header and exposes the full source plus evidence dock. The bottom action accounts for the device safe area.
- Focus, keyboard tabs, keyboard panel resizing, Escape, menu focus containment and correction-error recovery remain available. Viewer access explains why approval/downloads require an operator. Temporary correction errors preserve the user's form values.
- Product/workspace naming and profile import/export from the preceding upgrade remain functional. The finance primary action stays dark ink; configured accents apply to focus and evidence selection. The scoped `finance-workspace.css` lets the flagship calibration evolve without rewriting every legacy page at once. That choice retains some legacy CSS until the wider visual direction is approved.

Official references informed principles rather than copied branding or assets: [Linear's March 2026 interface refresh](https://linear.app/now/behind-the-latest-design-refresh) for quiet orientation and consistent header structure; [Stripe Invoicing](https://stripe.com/invoicing) for the operational invoice-table hierarchy; [Ramp accounts payable](https://ramp.com/accounts-payable) for the relationship between invoice processing, review and approvals. Public reference assets were inspected in private temporary files and are not shipped in the app.

## Run and demonstrate

From the InvoiceLens repository root:

```powershell
pwsh -NoProfile -File scripts/preview.ps1
```

Open **http://127.0.0.1:4312**; the isolated DEMO API is **http://127.0.0.1:8312**. The launcher uses existing dependencies and `data/preview/`, with local model simulation and no paid provider call. Choose **Use demo operator** at login.

Open `INV-0004.pdf` / invoice `001-26-0004` in Review queue. If it is absent in a fresh preview, upload `generated/invoicelens-fast/documents/INV-0004.pdf`. The fixture matches PO `HI-PO-00001`; its first line has a price variance. Inspect Findings, follow **Inspect line 1 evidence**, return to Details, and use a correction or an explicit finding decision before approving the server version. Approved versions expose CSV/XLSX/JSON downloads. A later correction invalidates the approval.

The UI test temporarily changes the synthetic issue date, records the QA reason, approves/exports, and restores the original source date. The final preview deliberately leaves that new version needing review. It does not change the original PDF or pretend the test correction came from a real customer.

## Evidence and checks

| Check | Result |
| --- | --- |
| Workspace/queue/intake helper regression | 10/10 passed |
| TypeScript | Passed, including production `tsc -b` |
| ESLint | Passed |
| Local OpenAPI contract | Passed: 22 routes, 26 typed schemas |
| Flagship real-browser journey | Passed: 6 groups, zero page errors; [result](screenshots/flagship-2026-10-06/qa-result.json) |
| Wider local-browser regression | Passed: 7 groups, zero page errors; [result](screenshots/regression-2026-10-06/qa-result.json) |
| Production bundle | Passed: Vite 7.3.6, 1574 modules, 3.87 seconds; [output](screenshots/flagship-2026-10-06/build-result.txt) |
| Full backend, bulk OCR, Docker, live provider quality | Not rerun for this frontend calibration |
| Formal screen-reader audit and physical mobile devices | Not run |

The browser checks used an isolated headless context of the user's local Chrome. No existing browser profile or tab was changed. The six flagship groups cover mobile evidence/action/Escape/menu focus, 1280/768 layouts, keyboard tabs/resizing/zoom, an explicitly injected 503 correction failure and successful retry, finding decision/approval/two valid XLSX downloads, and correction invalidation/real activity history. The wider regression covers login recovery, native upload and duplication, damaged-file rejection, search/filter clearing, appearance import/export/reset, PO review/reapproval, mobile layouts and a queue error/retry.

Comparable actual viewport screenshots:

- Desktop 1440 × 900: [before](screenshots/flagship-2026-10-06/before-desktop-1440.png), [after](screenshots/flagship-2026-10-06/after-desktop-1440.png).
- Mobile 390 × 844: [before](screenshots/flagship-2026-10-06/before-mobile-390.png), [after Details](screenshots/flagship-2026-10-06/after-mobile-390.png), [after Document](screenshots/flagship-2026-10-06/after-mobile-document-390.png).
- Additional layouts: [1280 × 800](screenshots/flagship-2026-10-06/after-responsive-1280.png), [768 × 1024](screenshots/flagship-2026-10-06/after-responsive-768.png).
- Real states: [findings](screenshots/flagship-2026-10-06/after-findings-desktop.png), [correction failure](screenshots/flagship-2026-10-06/after-correction-error-desktop.png), [approved](screenshots/flagship-2026-10-06/after-approved-desktop.png), [activity](screenshots/flagship-2026-10-06/after-activity-desktop.png).

Reproduce the main journey with the preview running and an already-installed Playwright module:

```powershell
$env:INVOICELENS_PLAYWRIGHT='<absolute path to an existing Playwright index.mjs>'
node scripts/qa-flagship.mjs
node scripts/qa-ui.mjs
```

Neither runner installs dependencies or a browser. Both mutate only the isolated synthetic preview. `--before` captures the baseline and `--capture-only` captures without review mutations; use a separate baseline checkout if recapturing the old design after these changes. A test outage is intentionally injected by the browser runner, not a reported live service incident.

Existing user changes in CI, ignore rules, handover/status documentation, backend fixtures and teaser assets were preserved. Nothing was pushed, deployed, published or modified in a sibling project.
