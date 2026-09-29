# InvoiceLens evaluation

## Final measured source revision — OCR enabled

On 2026-09-28, the final source revision processed all **300/300** rendered synthetic documents, including 90 scans, in a fresh isolated DEMO database. Tesseract 5.5.3 and the official English `tessdata_fast` model ran from this project's ignored `tmp` directory with one OCR thread. Jobs ran sequentially in batches of 20. The system exported its persisted predictions before the evaluator opened private truth. The machine-readable result, readable report, and actual predictions are archived as `evals/results/ocr-final-2026-09-28.{json,md}` and `evals/results/ocr-final-predictions-2026-09-28.json`.

| Held-out measurement | Actual numerator / denominator | Result | Target |
|---|---:|---:|---:|
| Native core fields | 150 / 150 | 100.0% | separately reported |
| Scanned core fields | 68 / 70 | 97.1% | separately reported |
| Combined core fields | 218 / 220 | 99.1% | 95% |
| Native line fields | 1,000 TP; 1,056 expected; 1,008 predicted | 96.9% F1 | separately reported |
| Scanned line fields | 526 TP; 558 expected; 549 predicted | 95.0% F1 | separately reported |
| Combined line fields | 1,526 TP; 1,614 expected; 1,557 predicted | 96.2% F1 | 90% |
| Finding precision, all emitted kinds | 70 / 122 predicted labels | **57.4%** | 90% |
| Finding recall, planted cases | 70 / 75 | 93.3% | 90% |

The extraction and finding-recall targets passed. **Finding precision did not**, so the quality release gate remains incomplete. The strict finding score counts every emitted kind, including source-quality and manual-selection warnings that are outside the six planted scenario kinds; it does not discard those warnings to improve the number. There were 52 false-positive and five false-negative document/kind pairs. Most false positives arose on scanned sources when OCR changed SKU characters, signs, amounts, or PO row quantities. A few are operational review warnings that correctly stop approval until a person resolves an uncertain source. The final report lists examples and per-field denominators. This benchmark is synthetic; it cannot establish accuracy on customer invoices or the untested CONNECTED model path.

## Complete local OCR measurement

On 2026-09-28, a fresh isolated DEMO run processed **all 300 rendered sources**, including 90 scans, using one sequential worker and Tesseract 5.5.3 with the official English `tessdata_fast` model. The Windows OCR tools lived in the project's ignored `tmp` directory; `OMP_THREAD_LIMIT=1` limited OCR to one thread. No runtime process read private scenario labels before prediction export. The first complete post-OCR-repair result is preserved in `evals/results/ocr-windows-baseline-2026-09-28.{json,md}`, with its prediction archive. It is a baseline for subsequent finding-rule corrections, not an estimate of customer accuracy.

| Held-out measurement | Actual numerator / denominator | Result | Target |
|---|---:|---:|---:|
| Native core fields | 150 / 150 | 100.0% | reported separately |
| Scanned core fields | 64 / 70 | 91.4% | reported separately |
| Combined core fields | 214 / 220 | 97.3% | 95% |
| Native line fields | 1,001 TP; 1,056 expected; 1,028 predicted | 96.1% F1 | reported separately |
| Scanned line fields | 526 TP; 558 expected; 552 predicted | 94.8% F1 | reported separately |
| Combined line fields | 1,527 TP; 1,614 expected; 1,580 predicted | 95.6% F1 | 90% |
| Finding precision | 67 / 139 predicted labels | 48.2% | 90% |
| Finding recall | 67 / 75 planted labels | 89.3% | 90% |

The baseline report preserves per-field denominators, 72 false-positive and eight false-negative finding pairs, and all 300 completed job statuses. The two extraction targets passed; the finding targets did not. General OCR parser and source-quality rule changes were then measured in the separate final run above.

To reproduce with Tesseract `eng` available on `PATH`, generate the full corpus and use the isolated runner. On a low-power machine, set `OMP_THREAD_LIMIT=1` and process queued jobs in batches instead of a single long command:

```powershell
$env:OMP_THREAD_LIMIT = '1'
& 'apps/api/.venv/Scripts/python.exe' evals/run_demo_evaluation.py --seed-only --database evals/results/invoicelens-ocr-recheck.db
& 'apps/api/.venv/Scripts/python.exe' evals/process_queued.py --database evals/results/invoicelens-ocr-recheck.db --limit 20
# Repeat process_queued.py until --status-only reports 300 complete, then:
& 'apps/api/.venv/Scripts/python.exe' evals/run_demo_evaluation.py --skip-processing --database evals/results/invoicelens-ocr-recheck.db
```

The separate capped Docker OCR baseline below was measured before the coordinate parser repair. A later continuous Docker attempt was interrupted by a full host system drive (162 complete, two failed, 136 queued). Its partial records were never scored. A bounded Docker script remains available in `scripts/evaluate-docker.ps1`, but this host's Docker image store subsequently reported an I/O error, so the complete post-repair measurement above used project-local Windows OCR instead.

## Initial container OCR measurement

The API image, with Tesseract 5.3.0 installed, processed all 300 synthetic sources in a single sequential run capped at two CPUs. All 300 jobs completed, including 90 scanned sources. The first held-out scanned core-field exact match was 44/70 (62.9%), while scanned line-field F1 was 0/558 because the OCR adapter had flattened TSV words into one line. Combined held-out core match was 194/220 (88.2%) and combined line F1 was 76.9%. Findings had 56/366 precision (15.3%) and 56/75 recall (74.7%); 310 false-positive pairs were driven chiefly by OCR missing fields and vendor-name contamination. The complete pre-repair result is preserved in `evals/results/ocr-baseline-2026-09-28.{json,md}` with its prediction archive. Coordinate-based OCR reconstruction and vendor matching corrections were included in the complete local OCR measurement above.

## Windows DEMO run without OCR

On 2026-09-28, after the parser and credit-note rendering fixes, `apps/api/.venv/Scripts/python.exe evals/run_demo_evaluation.py` processed all 300 rendered documents through the offline DEMO ingestion workflow. The run used a single sequential processing loop, an isolated SQLite database and storage, and project-local temporary files on D:. It accepted and processed 300 jobs, with 210 completed native documents and 90 failed scanned documents. All 90 failures were scanned sources with the same actionable error, `No readable text: install Tesseract OCR or upload a clearer source`; no native document failed. The predictor/exporter did not read ground truth before scoring.

| Measurement | Actual numerator / denominator | Result | Target |
|---|---:|---:|---:|
| Held-out native core fields | 150 / 150 | 100.0% | 95% combined |
| Held-out scanned core fields | 0 / 70 | 0.0% | reported separately |
| Held-out combined core fields | 150 / 220 | 68.2% | 95% |
| Held-out native line fields | 1,008 TP; 1,056 expected; 1,008 predicted | 97.7% F1 | 90% combined |
| Held-out scanned line fields | 0 TP; 558 expected; 0 predicted | 0.0% F1 | reported separately |
| Held-out combined line fields | 1,008 TP; 1,614 expected; 1,008 predicted | 76.9% F1 | 90% |
| Finding precision | 42 / 63 predicted labels | 66.7% | 90% |
| Finding recall | 42 / 75 planted labels | 56.0% | 90% |

All four combined release targets were unmet in this earlier no-OCR Windows run. The report has per-field denominators, 21 false-positive and 33 false-negative finding pairs, and the complete job status split. This measurement is preserved in `evals/results/final-demo-2026-09-28.json` and `.md`, with actual exported predictions in `evals/results/final-demo-predictions-2026-09-28.json`. The ordinary `latest.json` and `latest.md` now mirror the final OCR-enabled run above. The earlier offline score does not measure OCR, the CONNECTED model path, or real customer documents.

## Initial measured DEMO baseline

On 2026-09-28, `apps/api/.venv/Scripts/python.exe evals/run_demo_evaluation.py` submitted and processed all 300 rendered documents through the actual offline DEMO workflow, in a separate SQLite database and storage. The run used one sequential worker and no model API. It produced 210 completed native-text jobs and 90 failed scanned jobs. All 90 failures gave the actionable error `No readable text: install Tesseract OCR or upload a clearer source`; the environment has no Tesseract executable. No synthetic answer JSON was read until the persisted outputs had been exported as predictions.

| Measurement | Actual numerator / denominator | Result | Target |
|---|---:|---:|---:|
| Held-out native core fields | 130 / 150 | 86.7% | 95% combined |
| Held-out scanned core fields | 0 / 70 | 0.0% | reported separately |
| Held-out combined core fields | 130 / 220 | 59.1% | 95% |
| Held-out native line fields | 1,007 TP; 1,056 expected; 1,008 predicted | 97.6% F1 | 90% combined |
| Held-out scanned line fields | 0 TP; 558 expected; 0 predicted | 0.0% F1 | reported separately |
| Held-out combined line fields | 1,007 TP; 1,614 expected; 1,008 predicted | 76.8% F1 | 90% |
| Finding precision | 32 / 141 predicted labels | 22.7% | 90% |
| Finding recall | 32 / 75 planted labels | 42.7% | 90% |

**All four combined release targets remain unmet.** These are deterministic DEMO parser measurements, not CONNECTED model accuracy. The held-out native core errors concentrate in the invoice-number reader on layouts 9–10 (15 wrong numbers) and JPY thousands parsing on layout 12 (five wrong totals). The 109 false-positive finding pairs include 50 `MISSING_CURRENCY` and 21 `AMBIGUOUS_PO` flags. This baseline is preserved in `evals/results/baseline-demo-2026-09-28.json`, its companion `.md`, and the exported prediction JSON. The report lists every held-out core-field denominator, line-field numerator/denominator, and example false positives and negatives. Seven exporter/evaluator/generator tests pass; fixture tests are not counted as extraction quality.

After this baseline was measured, the 20 credit-note source files were repaired to print their PO numbers alongside the referenced invoice, and the deterministic parser received targeted fixes. The Windows run above measures the combined state without OCR. The initial baseline remains unchanged for comparison.

The brief's release targets remain at least 95% normalized core exact match, 90% line-field F1, and 90% finding precision and recall. A live-model or customer evaluation still needs separate, permissioned documents and labels. Any later improvements require a new measured run rather than editing this baseline.

## Run a blind application evaluation

With backend dependencies installed, the offline DEMO path can be run end to end using `python evals/run_demo_evaluation.py`. It sets an isolated SQLite database and storage under `evals/results`, submits all 300 public source files through the real seed/job pipeline, exports persisted predictions, and only then runs the evaluator against private truth. A rerun resets only that isolated DEMO database's demo workspaces. `--skip-processing` rescoring is available after a completed run.

1. Generate the full data: `python scripts/generate_dataset.py --preset full`.
2. Ingest the public `generated/invoicelens/manifest.json` through the normal application pipeline in evaluation workspaces. Do not provide `evals/data/full_ground_truth.json` to ingestion, retrieval, prompts, adapters, or correction UI.
3. Export the application's actual predictions as JSON. Preserve failures and missing documents rather than filling them with source truth. For the local DEMO backend, use a separate evaluation SQLite database, process every queued job, and run `python evals/export_demo_predictions.py --manifest generated/invoicelens/manifest.json --database evals/results/invoicelens-eval.db`. This reads only the public manifest and persisted workflow rows. It maps the backend's finding codes to the six scenario kinds; unmapped codes count as false positives. The exported shape is:

```json
{
  "schema_version": "1.0",
  "documents": [
    {
      "id": "INV-0001",
      "fields": {
        "vendor_name": "Printed vendor name",
        "invoice_number": "001-26-0001",
        "date": "2026-06-01",
        "currency": "USD",
        "total": "123.45"
      },
      "lines": [
        {"sku": "SKU", "description": "Description", "quantity": "2", "unit": "ea", "unit_price": "10.00", "line_amount": "20.00"}
      ],
      "findings": [{"kind": "unit_price_mismatch"}]
    }
  ]
}
```

4. Evaluate: `python evals/runner.py --predictions evals/results/demo_predictions.json`. The runner writes numeric results to `evals/results/latest.json` and a readable report to `evals/results/latest.md`. Missing or failed prediction documents remain in the denominator; unknown IDs are rejected. `python evals/runner.py` without predictions records inventory and pending status only.

The fixture at `evals/fixtures/evaluation_predictions.json` is intentionally imperfect. It checks that a missing document, an incorrect total, an incorrect quantity, and a false-positive finding reduce metrics. It is a test of the metric implementation, not a product accuracy sample.

## Metric definitions

- **Core normalized exact match:** per field, `correct / expected` for all held-out invoices. Reported separately for native and scanned documents, with `missing` and `incorrect` counts. Strings are whitespace-normalized and case-folded, currency uppercased, dates required in ISO `YYYY-MM-DD`, and amounts compared with `Decimal`.
- **Line-item field F1:** six fields (`sku`, `description`, `quantity`, `unit`, `unit_price`, `line_amount`) are scored as multisets. Non-SKU values are matched to the normalized SKU, so repeat SKU rows retain multiplicity. For each field: precision is `TP / predicted`, recall is `TP / expected`, F1 is `2TP / (expected + predicted)`. The report includes per-field numerators and denominators plus micro F1. Unmatched/missing rows lower recall; spurious rows lower precision.
- **Finding precision/recall:** exact `(document ID, finding kind)` pairs across all labeled scenarios. Precision is `TP / predicted labels`; recall is `TP / 75 expected labels`. Clean negatives and 20 legitimate lookalikes remain in the denominator for false positives. Overlapping cases contribute one pair per kind. Ambiguous vendor cases are reported explicitly, not silently treated as correct matches.
- **Splits:** development versus held-out vendor/layout IDs, and native versus scanned source. The evaluator reports every combination and a combined view. The primary extraction target is held-out/all media, but native and scanned results are both mandatory for interpretation. Findings use all scenario documents for the primary target.

## Deterministic checks versus probabilistic quality

Domain arithmetic, currency rounding, duplicate identifier rules, export formatting, and review state should be tested as deterministic software behavior in backend tests. The evaluator above measures extraction and finding outputs on rendered documents. A model fixture can establish schema/adapter contract behavior but cannot justify a real-model extraction score. Live evaluation needs a configured model, an explicit spending limit, and retained raw failure samples for human review. Any customer claim requires separate permissioned documents and independent labels; synthetic results are only engineering evidence.
