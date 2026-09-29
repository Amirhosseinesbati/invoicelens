# Synthetic demo dataset — data card

## Purpose and provenance

The dataset represents fictional B2B equipment distributor Harbor Industrial and 20 fictional suppliers. Names, addresses, emails under `example.test`, tax identifiers, purchase orders, invoices, amounts, and discrepancies are generated. It contains no customer documents, testimonials, or measured financial savings. The fixed default seed is `20260927` and the configurable reference date defaults to `2026-09-27`.

`scripts/generate_dataset.py` constructs exact structured source scenarios before rendering documents. It then draws native PDFs with ReportLab and rasterizes a fixed subset with Poppler and Pillow. The public `generated/invoicelens/manifest.json` contains only document ID, workspace, vendor ID, type, and relative file path. Structured source values and finding labels live solely in `evals/data/full_ground_truth.json`. Application ingestion must read the manifest and files, never the evaluator truth file.

## Measured generated inventory

The full generator completed on 2026-09-28 with these counts:

| Item | Count |
|---|---:|
| Rendered documents | 300 |
| Invoices | 220 |
| Purchase orders | 60 |
| Credit notes | 20 |
| Fictional vendors | 20 |
| Visual layout IDs | 12 |
| Invoice line items | 1,367 |
| Multi-page documents | 10 |
| Native-text PDFs | 210 |
| Rasterized source documents | 90 (30%) |
| Rasterized as image-only PDF / PNG / JPEG | 60 / 18 / 12 |

Each vendor has three purchase orders, eleven invoices, and one credit note. Invoices contain four to fourteen rows; some descriptions wrap and some SKUs repeat as separate partial-shipment rows. Amounts use USD, EUR, GBP, CAD, and JPY, with currency-specific rounding. Dates, thousand separators, decimal separators, tax rates, discounts, and freight vary. The rendered text contains explicit document, vendor, PO, date, currency, and total labels. Rasterization uses reproducible skew, contrast loss, blur, and light paper noise; a small subset has stronger damage. Every document visibly says `Synthetic demo dataset`.

## Splits and leakage control

| Split | Vendors | Layout IDs | Documents | Invoices | POs | Credit notes | Rasterized |
|---|---:|---|---:|---:|---:|---:|---:|
| Development | 16 | 1–8 | 240 | 176 | 48 | 16 | 72 |
| Held out | 4 | 9–12 | 60 | 44 | 12 | 4 | 18 |

Vendors never cross splits. Layouts 9–12 have distinct header geometry and are absent from development. The fixed split prevents a vendor-specific rule or template example from directly covering the held-out set. The generated reference date and seed may be changed, but the entity/layout split rule remains the same. Tests and model prompts must not read `evals/data`; production packaging should omit this directory entirely. Keeping evaluation truth in the source repository is for reproducibility, not a runtime feature.

## Planted findings and hard negatives

| Finding kind | Labeled occurrences |
|---|---:|
| Duplicate vendor/invoice identifier | 20 |
| Unit price differs from PO | 15 |
| Referenced PO does not exist | 11 |
| Invoiced quantity exceeds PO line | 13 |
| Printed total differs from Decimal calculation | 12 |
| Ambiguous printed vendor alias | 4 |
| **Total labels** | **75** |

Eight documents have overlapping labels. The truth file records each case independently, including referenced PO or duplicate ID and line index where relevant. PO-based mismatch labels are planted only when a resolvable PO number is printed. There are 233 documents without labeled findings. Twenty legitimate invoices deliberately resemble earlier bills in date, amount, and PO while retaining distinct invoice numbers; these are clean negatives for duplicate detection. Ambiguous vendor aliases are intentionally unresolved from printed name alone. The evaluator compares the text actually printed for vendor extraction and separately scores an `ambiguous_vendor_match` finding.

The source values of a wrong-price invoice still add up internally unless it also carries `total_inconsistent`. A quantity mismatch does not automatically imply an arithmetic error. This separation makes false positives measurable. Credit notes have negative quantity/amount and visibly print both the previous invoice reference and their PO number. Purchase orders and invoice histories are internally linked except where a missing PO is explicitly planted.

## Reproduction

Run from the project root in an environment with `reportlab`, `Pillow`, and Poppler `pdftoppm`:

```sh
uv run --project apps/api --frozen python scripts/generate_dataset.py --preset fast
uv run --project apps/api --frozen python scripts/generate_dataset.py --preset full
uv run --project apps/api --frozen python scripts/generate_dataset.py --preset full --seed 20260927 --reference-date 2026-09-27
uv run --project apps/api --frozen pytest -q evals/test_generator.py evals/test_runner.py evals/test_export_predictions.py
```

The fast preset produces five varied invoices and four referenced POs. Two of its documents are deliberately damaged raster images. It is for a responsive local demo, not a substitute for the 300-document acceptance run. `scripts/seed_demo.py` can generate and submit either public manifest through the backend's normal ingestion path; it never imports truth.

Bulk rendered files under `generated/` are reproducible and excluded from Git. Small source fixtures under `fixtures/` and evaluator contract fixtures under `evals/fixtures/` are tracked. Re-running into an existing generated directory replaces matching generated files and removes only paths from its earlier manifest that no longer belong to the new manifest.

## Limits

This corpus is synthetic and uses a small equipment vocabulary, one buyer, controlled typography, bounded scan damage, and deliberately constructed discrepancies. Its measured scores cannot establish accuracy on a customer's invoice population. A customer pilot needs representative, permissioned sample documents, label review, layout coverage, privacy controls, and an independently held-out acceptance set. The current environment has no Tesseract executable, so scanned OCR extraction quality is not measured by dataset generation.
