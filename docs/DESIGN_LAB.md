# InvoiceLens: archived local design comparison

These are reversible development previews from the visual-direction comparison. The user subsequently selected **A Command**; the [production workspace and themes](COMMAND_THEMES.md) now apply that direction across all seven pages. The archived A/B routes retain their original presentation. Both render the same React review components, API record, native synthetic PDF, source coordinates and version-bound approval rules. They are not new deployments or measured claims about live AI accuracy.

## Compare the directions

| | A — Command | B — Studio |
|---|---|---|
| Navigation | 72px accessible icon rail | Horizontal brand/navigation bar |
| Composition | White original document on the left; layered inspector on the right | Review dossier on the left; floating original document on the right |
| Visual language | Graphite/navy, subtle source illumination, restrained ice blue | Warm white, strong grotesk typography, ultramarine architectural document stage |
| Initial task | Findings first; actual price comparison leads the inspector | Two-column document identity; actual comparison leads the dossier |
| Intended tradeoff | Dense review work and direct evidence focus | Distinctive presentation and a more open identity hierarchy |

The comparison in the captured record is real validation output from the synthetic fixture: invoice unit price USD287.94, selected purchase-order unit price USD244.02, variance USD43.92. It comes from the finding details, not a hard-coded demo metric. If the record has no comparable price finding, the inspector presents its available finding or review guidance.

Both directions preserve field selection to actual page coordinates, line evidence, source zoom/download controls, keyboard review tabs, correction cancellation, and the existing approval barrier. When a finding blocks approval, **Review finding** is the available primary action. The mobile document view keeps the complete paper and evidence dock above its persistent action.

## Run and switch

From this repository root, with existing dependencies:

```powershell
pwsh -NoProfile -File scripts/preview.ps1
```

The web preview uses **4312**, API **8312**, and isolated synthetic state under `data/preview`. Use **Use demo operator** on the DEMO login. On a freshly initialized preview, upload `generated/invoicelens-fast/documents/INV-0004.pdf` if it is absent, then open the invoice.

Open either archived development route below to access the **Local design prototypes** selector:

- **A Command** appends `?design=command` to its document hash route.
- **B Studio** appends `?design=studio`.
- **Production** removes the parameter and returns to the selected production Command layout.

Current local record links:

- [A Command](http://127.0.0.1:4312/#/document/9c2f494879a34efb97f51eda195c5b76?design=command)
- [B Studio](http://127.0.0.1:4312/#/document/9c2f494879a34efb97f51eda195c5b76?design=studio)
- [Production](http://127.0.0.1:4312/#/document/9c2f494879a34efb97f51eda195c5b76)

Document IDs are local database identities; a newly uploaded record will have its own ID. Use the selector instead of copying another workspace's record link.

The selector and design query are development-only. The prototype stylesheet is conditionally imported in development; the production build excludes experimental components/styles while including the selected Command workspace. Switching archived directions writes no workspace appearance preferences or invoice changes. This document preserves the original comparison evidence; the current production screenshots and verification are in [COMMAND_THEMES.md](COMMAND_THEMES.md).

## Actual rendered evidence

Desktop captures are **1440×900**; mobile captures are **390×844** in an isolated headless context of the user's local Chrome, with reduced motion.

| Direction | Desktop | Mobile document reader |
|---|---|---|
| A Command | [Desktop](screenshots/design-lab-2026-10-07/command-desktop-1440.png) | [Mobile](screenshots/design-lab-2026-10-07/command-mobile-390.png) |
| B Studio | [Desktop](screenshots/design-lab-2026-10-07/studio-desktop-1440.png) | [Mobile](screenshots/design-lab-2026-10-07/studio-mobile-390.png) |

## Verification and limits

Passed on 2026-10-07:

- TypeScript `--noEmit`, ESLint, and all **12** frontend unit tests, including production query guard and valid preview-link handling.
- TypeScript build and Vite production build; prototype components and CSS absent from production assets.
- Five targeted UI groups across both directions: field-to-source selection, correction Escape, keyboard tabs, actual blocked approval, mobile reader/visible action/evidence dock clearance, menu Escape, no horizontal overflow, Current restoration and zero JavaScript page errors. See [machine-readable result](screenshots/design-lab-2026-10-07/qa-result.json).
- All four final captures visually inspected.

Earlier checks caught an obstructed B mobile menu and a few pixels of A dock/action overlap. The layer ordering and mobile source height were corrected, and the final repeat passed. The automation cancels correction forms and does not mutate invoice values or resolve findings.

`scripts/qa-design-lab.mjs` reuses an existing Playwright installation through `INVOICELENS_PLAYWRIGHT`; it does not install a browser or use the shared interactive browser.

Not run in this design pass: backend integration suite, bulk OCR/evaluation, connected model provider, Docker deployment, physical mobile devices or full screen-reader audit. They are separate from this local design decision.
