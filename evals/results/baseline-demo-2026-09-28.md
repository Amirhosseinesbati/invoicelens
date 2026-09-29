# InvoiceLens evaluation report

Generated: 2026-09-28T01:06:51.184823+00:00
Dataset: Synthetic demo dataset (seed 20260927, reference date 2026-09-27)

## Dataset inventory

300 documents; {'purchase_order': 60, 'invoice': 220, 'credit_note': 20}; 1367 invoice lines; 90 scanned documents; held-out layouts [9, 10, 11, 12]; 75 labeled findings.

Predictions: `evals/results/demo_predictions.json`

## Held-out extraction

| Medium | Invoices with predictions / expected | Core field exact match | Line field micro F1 |
|---|---:|---:|---:|
| native | 30 / 30 | 86.7% | 97.6% (1007 TP; 1056 expected; 1008 predicted) |
| scanned | 0 / 14 | 0.0% | 0.0% (0 TP; 558 expected; 0 predicted) |
| all | 30 / 44 | 59.1% | 76.8% (1007 TP; 1614 expected; 1008 predicted) |

Persisted job statuses: `{'complete': 210, 'failed': 90}`

### Per-field denominators (held-out, all media)

| Field | Correct / expected | Missing | Exact match |
|---|---:|---:|---:|
| vendor_name | 30 / 44 | 14 | 68.2% |
| date | 30 / 44 | 14 | 68.2% |
| currency | 30 / 44 | 14 | 68.2% |
| invoice_number | 15 / 44 | 14 | 34.1% |
| total | 25 / 44 | 14 | 56.8% |

| Line field | TP / expected | Predicted | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| sku | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| description | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| quantity | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| unit | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| unit_price | 168 / 269 | 168 | 100.0% | 62.5% | 76.9% |
| line_amount | 167 / 269 | 168 | 99.4% | 62.1% | 76.4% |

## Findings on all labeled scenarios

Precision 22.7% (32 / 141); recall 42.7% (32 / 75). False positives 109; false negatives 43; clean negative documents 233; ambiguous vendor labels 4.

False positive examples: `[{'id': 'CRN-0002', 'kind': 'po_missing'}, {'id': 'CRN-0004', 'kind': 'po_missing'}, {'id': 'CRN-0006', 'kind': 'po_missing'}, {'id': 'CRN-0008', 'kind': 'po_missing'}, {'id': 'CRN-0010', 'kind': 'po_missing'}, {'id': 'CRN-0012', 'kind': 'po_missing'}, {'id': 'CRN-0014', 'kind': 'po_missing'}, {'id': 'CRN-0016', 'kind': 'po_missing'}, {'id': 'CRN-0018', 'kind': 'duplicate_invoice'}, {'id': 'CRN-0018', 'kind': 'po_missing'}, {'id': 'CRN-0020', 'kind': 'po_missing'}, {'id': 'INV-0008', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0027', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0030', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0048', 'kind': 'total_inconsistent'}, {'id': 'INV-0049', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0049', 'kind': 'unmapped:line_amount_mismatch'}, {'id': 'INV-0051', 'kind': 'total_inconsistent'}, {'id': 'INV-0052', 'kind': 'total_inconsistent'}, {'id': 'INV-0052', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0054', 'kind': 'total_inconsistent'}, {'id': 'INV-0071', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0074', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0093', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0096', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0115', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0118', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0121', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0137', 'kind': 'unmapped:ambiguous_po'}, {'id': 'INV-0140', 'kind': 'unmapped:ambiguous_po'}]`

False negative examples: `[{'id': 'INV-0004', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0006', 'kind': 'quantity_mismatch'}, {'id': 'INV-0009', 'kind': 'duplicate_invoice'}, {'id': 'INV-0010', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0017', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0021', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0024', 'kind': 'po_missing'}, {'id': 'INV-0030', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0031', 'kind': 'duplicate_invoice'}, {'id': 'INV-0053', 'kind': 'duplicate_invoice'}, {'id': 'INV-0056', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0059', 'kind': 'total_inconsistent'}, {'id': 'INV-0062', 'kind': 'po_missing'}, {'id': 'INV-0069', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0075', 'kind': 'duplicate_invoice'}, {'id': 'INV-0081', 'kind': 'po_missing'}, {'id': 'INV-0082', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0095', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0096', 'kind': 'quantity_mismatch'}, {'id': 'INV-0097', 'kind': 'duplicate_invoice'}, {'id': 'INV-0100', 'kind': 'po_missing'}, {'id': 'INV-0108', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0119', 'kind': 'duplicate_invoice'}, {'id': 'INV-0119', 'kind': 'po_missing'}, {'id': 'INV-0120', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0131', 'kind': 'ambiguous_vendor_match'}, {'id': 'INV-0134', 'kind': 'unit_price_mismatch'}, {'id': 'INV-0138', 'kind': 'po_missing'}, {'id': 'INV-0141', 'kind': 'duplicate_invoice'}, {'id': 'INV-0141', 'kind': 'quantity_mismatch'}]`

## Target check

- held_out_core_exact_match: not met
- held_out_line_f1: not met
- finding_precision: not met
- finding_recall: not met

Matching rules: core strings are trimmed and case-folded; ISO dates are exact; monetary values compare as Decimal. Line fields use a multiset keyed by normalized SKU and value, preserving duplicate rows. Findings require exact document ID and kind. Missing prediction documents count as misses, and unknown finding kinds count as false positives. This synthetic score does not estimate real-customer accuracy.

