"""Summarize actual prediction errors after blind export; evaluator-only tool."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from runner import CORE_FIELDS, field_value, load_json, same_value


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    truth = load_json(ROOT / "evals" / "data" / "full_ground_truth.json")
    predictions = load_json(ROOT / "evals" / "results" / "demo_predictions.json")
    by_id = {item["id"]: item for item in predictions["documents"]}
    native_held = [d for d in truth["documents"] if d["type"] == "invoice" and d["split"] == "held_out" and not d["render"]["scanned"]]
    field_correct = {}
    for field in CORE_FIELDS:
        matches = 0
        for doc in native_held:
            expected = doc["source"]["printed_vendor_name"] if field == "vendor_name" else doc["source"]["number"] if field == "invoice_number" else doc["source"][field]
            matches += same_value(expected, field_value(by_id.get(doc["id"], {}), field), field)
        field_correct[field] = f"{matches}/{len(native_held)}"
    print("native_heldout_core", json.dumps(field_correct, indent=2))
    for field in ("invoice_number", "total"):
        errors = []
        for doc in truth["documents"]:
            if doc["type"] != "invoice" or doc["split"] != "held_out" or doc["render"]["scanned"]:
                continue
            expected = doc["source"]["number"] if field == "invoice_number" else doc["source"]["total"]
            actual = field_value(by_id.get(doc["id"], {}), field)
            if not same_value(expected, actual, field):
                errors.append({"id": doc["id"], "layout": doc["layout_id"], "expected": expected, "actual": actual})
        print(field, json.dumps(errors, indent=2))
    failures = Counter(item.get("processing_error", "") for item in predictions["documents"] if item.get("processing_status") == "failed")
    print("failure_reasons", json.dumps(failures, indent=2))
    codes = Counter(finding["kind"] for item in predictions["documents"] for finding in item.get("findings", []))
    print("predicted_finding_kinds", json.dumps(codes, indent=2))
    expected_pairs = {(doc["id"], finding["kind"]) for doc in truth["documents"] for finding in doc["expected_findings"]}
    predicted_pairs = {(item["id"], finding["kind"]) for item in predictions["documents"] for finding in item.get("findings", [])}
    print("false_positive_kinds", json.dumps(Counter(kind for _, kind in predicted_pairs - expected_pairs), indent=2))
    print("false_negative_kinds", json.dumps(Counter(kind for _, kind in expected_pairs - predicted_pairs), indent=2))
    by_truth_id = {doc["id"]: doc for doc in truth["documents"]}
    for kind in ("unmapped:missing_currency", "unmapped:ambiguous_po", "duplicate_invoice", "po_missing"):
        pairs = [(identifier, finding) for identifier, finding in predicted_pairs - expected_pairs if finding == kind]
        groups = Counter((by_truth_id[identifier]["type"], by_truth_id[identifier]["layout_id"]) for identifier, _ in pairs)
        print("false_positive_groups", kind, sorted(groups.items()))
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return
    for identifier in ("INV-0177", "INV-0189", "INV-0212"):
        doc = next(d for d in truth["documents"] if d["id"] == identifier)
        pdf = pdfium.PdfDocument((ROOT / "generated" / "invoicelens" / doc["render"]["path"]).read_bytes())
        page = pdf[0]
        text_page = page.get_textpage()
        excerpt = text_page.get_text_range()[:650]
        print("source_excerpt", identifier, repr(excerpt))
        text_page.close()
        page.close()
        pdf.close()


if __name__ == "__main__":
    main()
