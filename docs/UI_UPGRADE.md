# InvoiceLens workspace upgrade — 2026-10-06

This pass improves the existing evidence-first invoice pilot for portfolio demonstrations and client adaptation. All illustrated records are synthetic. The work does not establish live model quality, customer accuracy or accounting certification.

The subsequent [flagship review calibration](FLAGSHIP_DESIGN.md) superseded the review page and shell shown here. The selected [production Command workspace and themes](COMMAND_THEMES.md) now calibrate all seven workflows and provide the current handoff, screenshots and verification. This document preserves the first upgrade's functional scope and evidence.

## What changed

- The operations desk now suggests the next review using finding count and oldest receipt, shows an actionable distribution of actual document stages, and links failed/cancelled records to retry guidance. It does not mix currency totals or invent time-saved metrics.
- The review queue has one shared search value, status counts, document-type filters, four sort orders and incremental 25-record display. Processing includes uploaded and queued documents; retry includes cancelled documents. Clearing filters clears the global search too.
- Settings includes a previewable workspace appearance profile: product name, display name, indigo/teal/copper accent, comfortable/compact queue density and default queue view. The profile is scoped by authenticated workspace ID in browser storage. JSON import is bounded to 16 KB, version checked and allowlisted. A malformed import preserves the applied profile; unavailable storage leaves an explicit session-only message.
- A profile can be exported and imported into another browser or client workspace. The display name does not rename the server workspace, and the profile cannot configure credentials, financial rules, access or extraction behavior.
- Mobile review has explicit source/record controls. Selecting a field opens its source evidence. Changing documents remounts the review state, preventing a previous document's selected field, page, correction form or errors from leaking into the next record.
- Navigation includes current-page semantics, a skip link, a menu close control, Escape handling and keyboard focus containment. Record tabs support arrows, Home and End with associated tab-panel labels. Viewer export controls are disabled.
- Intake prevents duplicate local selections, empty/oversized files and silent truncation at its 30-file client limit. Selection is locked during submission; server validation and content-hash deduplication remain authoritative. The API currently permits up to 50 files, while the client intentionally caps one selection at 30.
- Login begins with empty credentials. Demo access and synthetic labels are offered only when the public API health endpoint reports DEMO. A failed sign-out is surfaced instead of claiming the server session ended.

## Local preview

From the repository root on Windows, using the existing locked dependencies:

```powershell
pwsh -NoProfile -File scripts/preview.ps1
```

Open **http://127.0.0.1:4312**. The API binds **http://127.0.0.1:8312**. The launcher uses `data/preview/` for a separate synthetic database, sources, checkpoints and logs. It does not reset the original demo, install dependencies or call a paid provider. It checks that both ports are free and stops only the API process it started when the foreground preview ends. Optional port flags are `-WebPort` and `-ApiPort`.

If `generated/invoicelens-fast/manifest.json` already exists, four prerequisite synthetic POs are seeded idempotently. Upload an `INV-*.pdf` from `generated/invoicelens-fast/documents/` to demonstrate intake and review. Otherwise, the workspace starts empty; use the existing README preparation instructions to generate the fixture. No real credentials or documents are needed.

This checkout had stale Windows dependency junctions after a folder rename. Existing package payloads were reused with `node scripts/repair-web-links.mjs` (dry run), then `node scripts/repair-web-links.mjs --apply`. The script only replaces verified junctions inside this project's `apps/web/node_modules`; it does not download packages. The preview launcher supplies the local Python source path for a relocated editable environment. A normal clean checkout should use the existing locked install instructions instead.

## Reuse for a client

1. Configure the real server workspace, access, locale and extraction adapter through the existing deployment procedures.
2. Set optional public build defaults using `apps/web/.env.example`: `VITE_PRODUCT_NAME`, `VITE_WORKSPACE_LABEL` and `VITE_ACCENT`. Leave the workspace label blank to inherit the authenticated workspace name. Invalid build-profile values fall back to InvoiceLens defaults.
3. Use Settings to create and preview a client profile, apply it, then export the applied JSON. Import into the target browser/workspace and apply. Browser preferences override build defaults; Reset appearance restores installation defaults.
4. For the current production design, adapt semantic tokens in `apps/web/public/theme-base.css` and scoped layouts in `apps/web/src/command-workspace.css`; keep status colors semantic and source-paper colors intact. Queue filtering, intake selection and profile validation remain separate pure TypeScript modules. See [the current theme/configuration boundaries](COMMAND_THEMES.md).
5. Calibrate customer layouts and export mappings independently. UI configuration does not make the synthetic benchmark a customer measurement.

`VITE_API_PROXY_TARGET` controls the development proxy. Browser requests remain same-origin. Never place provider keys or server secrets in `VITE_*` variables. In a production build these display defaults are public and require a rebuild to change; Settings profiles are per browser, not organization-wide configuration.

## Verification for this pass

| Check | Outcome |
|---|---|
| Node workspace/queue/intake regression suite | 10/10 passed |
| TypeScript `tsc --noEmit` | Passed |
| ESLint | Passed |
| API contract against the local FastAPI OpenAPI | Passed: 22 routes, 26 typed schemas |
| Real local Chrome UI smoke | Passed: 7 workflow groups, zero page errors, 14 desktop/mobile screenshots; [machine-readable result](screenshots/upgrade-2026-10-06/qa-result.json) |
| Production build | Passed: TypeScript build + Vite 7.3.6, 1,573 modules, 3.37s; [exact output](screenshots/upgrade-2026-10-06/build-result.txt) |
| Full backend suite, Docker, bulk OCR and live model evaluation | Not rerun: backend behavior was retained; this pass used a small native synthetic workflow |

Lightweight checks use the existing dependencies:

```powershell
Set-Location apps/web
node --test tests/workbench.test.mjs
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js .
node scripts/check-openapi-strict.mjs http://127.0.0.1:8312/openapi.json
```

Reproduce production bundling without reinstalling dependencies:

```powershell
# From apps/web
node node_modules/vite/bin/vite.js build
```

The optional smoke runner is `node scripts/qa-ui.mjs` from the repository root while the preview is running. It requires an existing Playwright module and local Chrome. Set `INVOICELENS_PLAYWRIGHT` to an absolute existing module entry path when Playwright is supplied by the local tooling environment. It never installs a browser. The runner mutates only the isolated synthetic preview data and saves screenshots/test exports inside this project. It tests login recovery, local file validation, native upload and duplicate handling, damaged-PDF rejection, search clearing, profile reload/import/export/reset, source review, keyboard tabs, approval and repeat downloads, correction/reapproval, mobile panels, and an explicitly injected 503/retry state. That injected outage is test evidence, not a claim that the live service failed.

Screenshots are in [upgrade-2026-10-06](screenshots/upgrade-2026-10-06), with 1440×1000 desktop and 390×844 mobile views. The UI was inspected in an isolated headless session of the user's local Chrome; shared interactive browser tools were unavailable. Existing September screenshots, benchmark results and user-edited handover/CI files were preserved.

## Remaining boundaries

The appearance profile is local browser configuration, not a multi-user settings service. The queue fetches the current server document list and limits rendered rows; it is not server-side pagination. Upload limits are currently based on the existing 20 MB default, so a customer installation with a different server limit needs coordinated client configuration. Formal screen-reader auditing, mobile real-device testing and live-provider/customer-layout evaluation remain separate checks. The existing synthetic finding-precision release gate is still incomplete.
