"""Non-perfect fixture verifies denominators, misses and false positives."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS))

from runner import evaluate, load_json  # noqa: E402


class EvaluatorTests(unittest.TestCase):
    def test_counts_missing_document_and_false_positive(self) -> None:
        truth = load_json(EVALS / "fixtures" / "evaluation_truth.json")
        predictions = load_json(EVALS / "fixtures" / "evaluation_predictions.json")
        result = evaluate(truth, predictions)
        held = result["splits"]["held_out"]["all"]["extraction"]
        self.assertEqual(held["predicted_invoices"], 1)
        self.assertEqual(held["invoices"], 2)
        self.assertEqual(held["core_fields"]["total"]["correct"], 0)
        self.assertEqual(held["core_fields"]["total"]["missing"], 1)
        self.assertEqual(held["core_micro_exact_match"], 0.4)
        self.assertEqual(held["line_micro"]["true_positive"], 11)
        self.assertEqual(held["line_micro"]["expected"], 18)
        self.assertEqual(held["line_micro"]["predicted"], 12)
        self.assertAlmostEqual(held["line_micro"]["f1"], 22 / 30)
        findings = result["splits"]["all"]["all"]["findings"]
        self.assertEqual((findings["true_positive"], findings["expected"], findings["predicted"]), (1, 1, 2))
        self.assertEqual(findings["precision"], 0.5)
        self.assertEqual(findings["recall"], 1.0)
        self.assertEqual(findings["clean_negative_documents"], 1)

    def test_no_predictions_does_not_claim_quality(self) -> None:
        truth = load_json(EVALS / "fixtures" / "evaluation_truth.json")
        result = evaluate(truth, None)
        self.assertEqual(result["quality_status"], "pending_predictions")
        self.assertNotIn("splits", result)


if __name__ == "__main__":
    unittest.main()
