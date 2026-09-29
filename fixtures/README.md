# Small source fixtures

These four documents are fictional rendered sources copied from the reproducible full dataset with seed `20260927` and reference date `2026-09-27`:

- `documents/PO-0001.pdf`: native-text purchase order.
- `documents/INV-0004.pdf`: native-text invoice with a PO unit-price mismatch.
- `documents/INV-0002.png`: lightly damaged raster invoice.
- `documents/CRN-0001.jpg`: raster credit note.

They contain no machine-readable scenario answers or finding labels. Ground truth belongs under `evals/data`; tests and demos must not mount that directory as runtime input. Generate the full 300-document set with `python scripts/generate_dataset.py --preset full`.
