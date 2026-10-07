# InvoiceLens production Command workspace — 2026-10-07

The selected **A Command** direction is now the production default across the operations desk, review queue, batch intake, vendors, exports, workspace settings and document review. Fresh browsers start in **Dark**. **Light** has its own cool white/blue palette, and **System** follows the device preference. All illustrated data is synthetic; this design pass makes no new live AI accuracy or customer performance claim.

## Product and review behavior

The compact navigation rail, visible page titles and consistent toolbar organize the seven workflows. The overview uses actual stage counts and links into review work. Queue filters and appearance profiles retain their existing behavior. Intake, vendor tables, export history, settings, empty states and retry states share the same semantic surfaces and typography. Mobile navigation, source/record controls, evidence dock and persistent review action remain usable at 390px; tablet layouts were also checked at 768px and 1024px.

Document review opens on Findings and presents a real unit-price comparison when the current finding contains one. **Review finding** leads to the original source coordinates when approval is blocked. Approval remains bound to the document version and existing role/validation rules. The native paper stays readable beside the inspector, with no theme filter applied to the PDF image. Media downloads and accounting exports keep their original formats and values.

The demonstration invoice in the captures is `INV-0004.pdf`, with an actual synthetic finding comparing USD287.94 against PO USD244.02, a USD43.92 difference. That comparison comes from API finding details; it is not a fabricated success metric. Local document IDs and record versions may differ in another installation.

## Theme architecture and client reuse

- `apps/web/public/theme-base.css` defines semantic canvas, rail, surface, text, border, accent, status, evidence, source-stage and chart tokens for both themes. Its native `color-scheme` declaration also styles browser controls. Existing Indigo/Teal/Copper choices have corresponding light and dark accents.
- `apps/web/public/theme-init.js` runs synchronously in the document head before React. It validates the stored preference, resolves System, applies the theme and updates the browser theme color. It uses an external same-origin script and stylesheet, without inline execution. The isolated CSP check verifies a saved Light preference at first paint while inline scripts are blocked; it is not a deployment-wide CSP certification.
- The external store in `apps/web/src/lib/theme.ts` has stable snapshots. Only the theme controls subscribe. Theme changes update root attributes instead of remounting the application, invalidating business queries or resetting forms. The OS listener exists only while System is selected.
- `invoicelens:theme:v1` is a global display preference for this browser/origin. It accepts only `dark`, `light` or `system`; corrupt/missing values fall back to Dark. If storage is denied, switching still works for the session. Another tab's valid changes are synchronized.
- The existing version-1 workspace appearance JSON remains workspace-scoped. It controls branding, accent, queue density and default view; it deliberately does not export the browser's theme preference. Resetting that profile restores its installation defaults.
- `apps/web/src/command-workspace.css` owns the production shell and page presentation. For a client adaptation, change the semantic tokens and public branding defaults first, then adjust these scoped layouts. Keep status meaning, readable contrast and source-paper colors intact. Never place credentials in `VITE_*` display configuration.

The development A/B review experiments remain available through `?design=command` and `?design=studio`. They retain their original presentation and do not inherit the production theme toolbar. Their **Production** link returns to the selected Command workspace. Query handling and prototype components/styles are development-only; production bundles include the selected design and real comparison, without the experimental Studio stylesheet or selector. See the [historical design comparison](DESIGN_LAB.md).

## Local preview

From this repository root, using already installed dependencies:

```powershell
pwsh -NoProfile -File scripts/preview.ps1
```

Open **http://127.0.0.1:4312**. The API uses **http://127.0.0.1:8312**, and synthetic preview state is isolated under `data/preview/`. The launcher does not install packages, reset the original demo or call a paid provider. Use **Use demo operator** when DEMO is confirmed. If no invoices are present, upload the native synthetic PDFs from `generated/invoicelens-fast/documents/`; fixture preparation remains covered in the README.

## Verification and rendered evidence

Passed on 2026-10-07:

| Check | Result |
|---|---|
| TypeScript no-emit and ESLint | Passed |
| Frontend tests | 17/17 passed, including theme persistence, OS listener lifecycle, denied storage, input validation, stable snapshots and semantic text/status/control contrast |
| Production TypeScript + Vite build | Passed; same-origin bootstrap assets and production Command included; development prototypes excluded |
| Local API/OpenAPI contract | Passed: 22 routes, 26 typed schemas |
| Production theme/browser checks | 10 groups passed, zero JavaScript page errors; all seven pages in both themes, mobile/tablet overflow, retained draft/DOM/navigation/media, no theme-triggered API fetch, persisted reload, live System changes, denied storage, injected 503/retry and saved Light at first paint under restrictive CSP |
| Existing functional regression | 7 groups passed; login recovery, native intake/deduplication, search, profile import/export/reload, evidence/keyboard review, version approval, repeated XLSX downloads, correction/reapproval, mobile navigation and 503 recovery |
| Archived A/B regression | 5 groups passed, zero JavaScript page errors |

Results and captures: [theme QA](screenshots/command-themes-2026-10-07/qa-result.json), [production build](screenshots/command-themes-2026-10-07/build-result.txt), [functional regression](screenshots/command-regression-2026-10-07/qa-result.json), [archived prototypes](screenshots/archive-regression-2026-10-07/qa-result.json).

| View | Dark | Light |
|---|---|---|
| Review, 1440×900 | [Rendered review](screenshots/command-themes-2026-10-07/document-dark-1440.png) | [Rendered review](screenshots/command-themes-2026-10-07/document-light-1440.png) |
| Operations, 1440×900 | [Rendered overview](screenshots/command-themes-2026-10-07/overview-dark-1440.png) | [Rendered overview](screenshots/command-themes-2026-10-07/overview-light-1440.png) |
| Source reader, 390×844 | [Rendered mobile](screenshots/command-themes-2026-10-07/review-dark-390.png) | [Rendered mobile](screenshots/command-themes-2026-10-07/review-light-390.png) |

Captures use an isolated headless session of the **user's local Chrome**, not the shared interactive browser. Both palettes and mobile/tablet renders were visually inspected. Injected errors are explicitly synthetic test conditions. Earlier verification caught inherited white surfaces and insufficient faint-label contrast on inset light surfaces; these were corrected before the final repeat. The existing functional runner was updated to open Details explicitly because the selected design now starts on Findings; all workflow assertions remain.

To reproduce checks without reinstalling dependencies:

```powershell
# From apps/web
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js .
node --test tests/*.test.mjs
node scripts/check-openapi-strict.mjs http://127.0.0.1:8312/openapi.json
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build

# From the repository root with the preview running
# Set INVOICELENS_PLAYWRIGHT to an existing Playwright module entry path.
node scripts/qa-command.mjs
$env:INVOICELENS_QA_DIR='docs/screenshots/command-regression-2026-10-07'
node scripts/qa-ui.mjs
$env:INVOICELENS_DESIGN_QA_DIR='docs/screenshots/archive-regression-2026-10-07'
node scripts/qa-design-lab.mjs
```

The browser runners require an existing Playwright installation and local Chrome. They do not install browsers. The functional runner mutates only the isolated synthetic preview records; the theme runner cancels correction drafts and does not approve or resolve the illustrated invoice.

## Remaining boundaries

No push, publishing or deployment was performed. The full backend integration suite, bulk OCR/evaluation, Docker deployment, connected model provider, physical mobile testing and formal screen-reader audit were not rerun in this UI pass. Semantic color tests and browser checks support the checked cases; they are not a full WCAG audit. The synthetic finding-precision release gate remains incomplete. Per-browser settings, client/server upload-limit coordination and server-side queue pagination remain the previously documented pilot limits.
