# InvoiceLens evaluation report

Generated: 2026-09-28T07:27:29.302405+00:00
Dataset: Synthetic demo dataset (seed 20260927, reference date 2026-09-27)

## Dataset inventory

300 documents; {'purchase_order': 60, 'invoice': 220, 'credit_note': 20}; 1367 invoice lines; 90 scanned documents; held-out layouts [9, 10, 11, 12]; 75 labeled findings.

Predictions: `/workspace/evals/results/demo_predictions.json`

## Held-out extraction

| Medium | Invoices with predictions / expected | Core field exact match | Line field micro F1 |
|---|---:|---:|---:|
| native | 30 / 30 | 100.0% | 97.7% (1008 TP; 1056 expected; 1008 predicted) |
| scanned | 14 / 14 | 62.9% | 0.0% (0 TP; 558 expected; 0 predicted) |
| all | 44 / 44 | 88.2% | 76.9% (1008 TP; 1614 expected; 1008 predicted) |

Persisted job statuses: `{'complete': 300}`

### Per-field denominators (held-out, all media)

| Field | Correct / expected | Missing | Exact match |
|---|---:|---:|---:|
| vendor_name | 39 / 44 | 1 | 88.6% |
| date | 43 / 44 | 1 | 97.7% |
| currency | 41 / 44 | 3 | 93.2% |
| invoice_number | 41 / 44 | 0 | 93.2% |
| total | 30 / 44 | 14 | 68.2% |

| Line field | TP / expected | Predicted | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| sku | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| description | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| quantity | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| unit | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| unit_price | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| line_amount | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |

## Findings on all labeled scenarios

Precision 15.3% (56 / 366); recall 74.7% (56 / 75). False positives 310; false negatives 19; clean negative documents 233; ambiguous vendor labels 4.

False positive examples: `[{'id': 'CRN-0001', 'kind': 'unmapped:missing_currency'}, {'id': 'CRN-0001', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0003', 'kind': 'unmapped:missing_currency'}, {'id': 'CRN-0003', 'kind': 'unmapped:missing_date'}, {'id': 'CRN-0003', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0005', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0007', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0009', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0011', 'kind': 'unmapped:missing_currency'}, {'id': 'CRN-0011', 'kind': 'unmapped:missing_date'}, {'id': 'CRN-0011', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0013', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0015', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0017', 'kind': 'unmapped:missing_total'}, {'id': 'CRN-0019', 'kind': 'unmapped:missing_total'}, {'id': 'INV-0001', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0002', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0002', 'kind': 'po_missing'}, {'id': 'INV-0002', 'kind': 'unmapped:missing_currency'}, {'id': 'INV-0002', 'kind': 'unmapped:missing_total'}, {'id': 'INV-0003', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0003', 'kind': 'duplicate_invoice'}, {'id': 'INV-0004', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0005', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0006', 'kind': 'po_missing'}, {'id': 'INV-0006', 'kind': 'unmapped:missing_currency'}, {'id': 'INV-0006', 'kind': 'unmapped:missing_total'}, {'id': 'INV-0007', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0008', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0008', 'kind': 'unmapped:po_selection_required'}]`

False negative examples: `[{'id': 'INV-0006', 'kind': 'quantity_mismatch'}, {'id': 'INV-0021', 'kind': 'quantity_mismatch'}, {'id': 'INV-0030', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0031', 'kind': 'duplicate_invoice'}, {'id': 'INV-0056', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0059', 'kind': 'total_inconsistent'}, {'id': 'INV-0096', 'kind': 'quantity_mismatch'}, {'id': 'INV-0119', 'kind': 'duplicate_invoice'}, {'id': 'INV-0120', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0131', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0134', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0141', 'kind': 'quantity_mismatch'}, {'id': 'INV-0144', 'kind': 'total_inconsistent'}, {'id': 'INV-0147', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0156', 'kind': 'quantity_mismatch'}, {'id': 'INV-0160', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0178', 'kind': 'total_inconsistent'}, {'id': 'INV-0185', 'kind': 'duplicate_invoice'}, {'id': 'INV-0216', 'kind': 'quantity_mismatch'}]`

## Target check

- held_out_core_exact_match: not met
- held_out_line_f1: not met
- finding_precision: not met
- finding_recall: not met

Matching rules: core strings are trimmed and case-folded; ISO dates are exact; monetary values compare as Decimal. Line fields use a multiset keyed by normalized SKU and value, preserving duplicate rows. Findings require exact document ID and kind. Missing prediction documents count as misses, and unknown finding kinds count as false positives. This synthetic score does not estimate real-customer accuracy.

