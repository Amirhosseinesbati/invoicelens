# InvoiceLens evaluation report

Generated: 2026-09-28T09:25:58.061565+00:00
Dataset: Synthetic demo dataset (seed 20260927, reference date 2026-09-27)

## Dataset inventory

300 documents; {'purchase_order': 60, 'invoice': 220, 'credit_note': 20}; 1367 invoice lines; 90 scanned documents; held-out layouts [9, 10, 11, 12]; 75 labeled findings.

Predictions: `evals/results/demo_predictions.json`

## Held-out extraction

| Medium | Invoices with predictions / expected | Core field exact match | Line field micro F1 |
|---|---:|---:|---:|
| native | 30 / 30 | 100.0% | 96.9% (1000 TP; 1056 expected; 1008 predicted) |
| scanned | 14 / 14 | 97.1% | 95.0% (526 TP; 558 expected; 549 predicted) |
| all | 44 / 44 | 99.1% | 96.2% (1526 TP; 1614 expected; 1557 predicted) |

Persisted job statuses: `{'complete': 300}`

### Per-field denominators (held-out, all media)

| Field | Correct / expected | Missing | Exact match |
|---|---:|---:|---:|
| vendor_name | 44 / 44 | 0 | 100.0% |
| date | 44 / 44 | 0 | 100.0% |
| currency | 44 / 44 | 0 | 100.0% |
| invoice_number | 43 / 44 | 0 | 97.7% |
| total | 43 / 44 | 1 | 97.7% |

| Line field | TP / expected | Predicted | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| sku | 260 / 269 | 261 | 99.6% | 96.7% | 98.1% |
| description | 236 / 269 | 261 | 90.4% | 87.7% | 89.1% |
| quantity | 250 / 269 | 252 | 99.2% | 92.9% | 96.0% |
| unit | 260 / 269 | 261 | 99.6% | 96.7% | 98.1% |
| unit_price | 260 / 269 | 261 | 99.6% | 96.7% | 98.1% |
| line_amount | 260 / 269 | 261 | 99.6% | 96.7% | 98.1% |

## Findings on all labeled scenarios

Precision 56.0% (70 / 125); recall 93.3% (70 / 75). False positives 55; false negatives 5; clean negative documents 233; ambiguous vendor labels 4.

False positive examples: `[{'id': 'CRN-0001', 'kind': 'total_inconsistent'}, {'id': 'CRN-0003', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'CRN-0005', 'kind': 'total_inconsistent'}, {'id': 'CRN-0007', 'kind': 'total_inconsistent'}, {'id': 'CRN-0011', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'CRN-0015', 'kind': 'total_inconsistent'}, {'id': 'CRN-0015', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'CRN-0017', 'kind': 'total_inconsistent'}, {'id': 'INV-0002', 'kind': 'total_inconsistent'}, {'id': 'INV-0002', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'INV-0008', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0008', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0009', 'kind': 'unmapped:missing_currency'}, {'id': 'INV-0009', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0010', 'kind': 'unmapped:po_selection_required'}, {'id': 'INV-0018', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0018', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0021', 'kind': 'unmapped:po_selection_required'}, {'id': 'INV-0028', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0046', 'kind': 'quantity_mismatch'}, {'id': 'INV-0046', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0049', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0049', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0062', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'INV-0075', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0078', 'kind': 'unmapped:sku_not_on_po'}, {'id': 'INV-0084', 'kind': 'total_inconsistent'}, {'id': 'INV-0084', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0084', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'INV-0084', 'kind': 'unmapped:sku_not_on_po'}]`

False negative examples: `[{'id': 'INV-0021', 'kind': 'quantity_mismatch'}, {'id': 'INV-0075', 'kind': 'duplicate_invoice'}, {'id': 'INV-0120', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0131', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0185', 'kind': 'duplicate_invoice'}]`

## Target check

- held_out_core_exact_match: met
- held_out_line_f1: met
- finding_precision: not met
- finding_recall: met

Matching rules: core strings are trimmed and case-folded; ISO dates are exact; monetary values compare as Decimal. Line fields use a multiset keyed by normalized SKU and value, preserving duplicate rows. Findings require exact document ID and kind. Missing prediction documents count as misses, and unknown finding kinds count as false positives. This synthetic score does not estimate real-customer accuracy.

