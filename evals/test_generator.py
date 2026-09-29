"""Verify scenario invariants independently of how invoices are drawn."""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_dataset import DEFAULT_REFERENCE_DATE, SEED, build_scenarios, render_pdf  # noqa: E402


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = build_scenarios(SEED, DEFAULT_REFERENCE_DATE)

    def test_counts_and_partition(self) -> None:
        docs = self.documents
        self.assertEqual(Counter(d["type"] for d in docs), {"invoice": 220, "purchase_order": 60, "credit_note": 20})
        self.assertEqual(len({d["id"] for d in docs}), 300)
        self.assertEqual(len({d["vendor_id"] for d in docs}), 20)
        self.assertEqual({d["layout_id"] for d in docs if d["split"] == "held_out"}, {9, 10, 11, 12})
        self.assertFalse({d["vendor_id"] for d in docs if d["split"] == "held_out"} & {d["vendor_id"] for d in docs if d["split"] == "development"})
        self.assertEqual(sum(len(d["source"]["lines"]) for d in docs if d["type"] == "invoice"), 1367)

    def test_money_and_labeled_total_anomalies(self) -> None:
        for doc in self.documents:
            source = doc["source"]
            currency = source["currency"]
            q = Decimal("1") if currency == "JPY" else Decimal("0.01")
            subtotal = sum((Decimal(row["line_amount"]) for row in source["lines"]), Decimal("0"))
            self.assertEqual(subtotal, Decimal(source["subtotal"]))
            for row in source["lines"]:
                self.assertEqual((Decimal(row["quantity"]) * Decimal(row["unit_price"])).quantize(q, rounding=ROUND_HALF_UP), Decimal(row["line_amount"]))
            computed = Decimal(source["subtotal"]) + Decimal(source["tax"]) + Decimal(source["freight"]) - Decimal(source["discount"])
            self.assertEqual(computed, Decimal(source["computed_total"]))
            has_total_label = any(f["kind"] == "total_inconsistent" for f in doc["expected_findings"])
            self.assertEqual(Decimal(source["total"]) != computed, has_total_label)

    def test_findings_and_clean_hard_negatives(self) -> None:
        docs = self.documents
        findings = [finding for doc in docs for finding in doc["expected_findings"]]
        self.assertGreaterEqual(len(findings), 50)
        self.assertEqual(sum(d["lookalike_legitimate"] for d in docs if d["type"] == "invoice"), 20)
        self.assertGreater(sum(len(d["expected_findings"]) > 1 for d in docs), 0)
        for doc in docs:
            if doc.get("lookalike_legitimate"):
                self.assertFalse(doc["expected_findings"])

    def test_credit_note_prints_reference_and_po_number(self) -> None:
        import pypdfium2

        note = next(d for d in self.documents if d["type"] == "credit_note")
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as folder:
            path = Path(folder) / "credit-note.pdf"
            render_pdf(note, path)
            pdf = pypdfium2.PdfDocument(str(path))
            try:
                printed = pdf[0].get_textpage().get_text_range()
            finally:
                pdf.close()
        self.assertIn(f"Reference: {note['source']['reference_invoice']}", printed)
        self.assertIn(f"PO #: {note['source']['po_number']}", printed)


if __name__ == "__main__":
    unittest.main()
