"""Evaluate independent InvoiceLens predictions against private synthetic truth.

No model is run here. Predictions must be exported from the application under
test. With no predictions, the runner records dataset inventory and pending
quality status rather than fabricating an accuracy score.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRUTH = ROOT / "evals" / "data" / "full_ground_truth.json"
DEFAULT_RESULT = ROOT / "evals" / "results" / "latest.json"
DEFAULT_REPORT = ROOT / "evals" / "results" / "latest.md"
CORE_FIELDS = ("vendor_name", "date", "currency", "invoice_number", "total")
LINE_FIELDS = ("sku", "description", "quantity", "unit", "unit_price", "line_amount")
FINDING_KINDS = {
    "duplicate_invoice", "unit_price_mismatch", "po_missing",
    "quantity_mismatch", "total_inconsistent", "ambiguous_vendor_match",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise ValueError(f"Expected a JSON object with documents list: {path}")
    return data


def field_value(record: dict[str, Any], key: str) -> Any:
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else record
    value = fields.get(key)
    if value is None:
        synonyms = {
            "invoice_number": ("number", "document_number", "invoice_no"),
            "vendor_name": ("vendor", "supplier_name"),
            "date": ("invoice_date",),
            "total": ("amount_due",),
        }
        for candidate in synonyms.get(key, ()):
            if candidate in fields:
                value = fields[candidate]
                break
    if isinstance(value, dict):
        for candidate in ("normalized_value", "value", "normalized", "raw_value"):
            if candidate in value:
                return value[candidate]
    if key == "vendor_name" and isinstance(value, dict):
        return value.get("name")
    return value


def normalize(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if field in {"total", "quantity", "unit_price", "line_amount"}:
        try:
            return format(Decimal(str(value).replace(",", "")), "f")
        except InvalidOperation:
            return f"invalid:{value}"
    text = re.sub(r"\s+", " ", str(value).strip())
    if field == "currency":
        return text.upper()
    if field == "date":
        return text  # normalized ISO-8601 is required from the system under test
    return text.casefold()


def same_value(expected: Any, actual: Any, field: str) -> bool:
    left, right = normalize(expected, field), normalize(actual, field)
    if field in {"total", "quantity", "unit_price", "line_amount"} and left is not None and right is not None:
        try:
            return Decimal(left) == Decimal(right)
        except InvalidOperation:
            return False
    return left == right


def predicted_lines(record: dict[str, Any]) -> list[dict[str, Any]]:
    lines = record.get("lines", record.get("line_items", []))
    if not isinstance(lines, list):
        return []
    return [line for line in lines if isinstance(line, dict)]


def line_tokens(lines: list[dict[str, Any]], field: str) -> Counter[Any]:
    tokens: Counter[Any] = Counter()
    for line in lines:
        raw = field_value(line, field)
        value = normalize(raw, field)
        if value is None:
            continue
        sku = normalize(field_value(line, "sku"), "sku")
        if field == "sku":
            tokens[value] += 1
        elif sku is not None:
            tokens[(sku, value)] += 1
        else:
            tokens[("<missing-sku>", value)] += 1
    return tokens


def prediction_index(predictions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in predictions["documents"]:
        if not isinstance(item, dict) or not item.get("id"):
            raise ValueError("Every prediction document must have an id")
        key = str(item["id"])
        if key in index:
            raise ValueError(f"Duplicate prediction id: {key}")
        index[key] = item
    return index


def findings_for(record: dict[str, Any] | None) -> set[str]:
    if record is None:
        return set()
    values = record.get("findings", [])
    if not isinstance(values, list):
        return set()
    found: set[str] = set()
    for value in values:
        kind = value.get("kind", value.get("code")) if isinstance(value, dict) else value
        if kind is not None:
            found.add(str(kind))
    return found


def metric(tp: int, expected: int, predicted: int) -> dict[str, Any]:
    return {
        "true_positive": tp,
        "expected": expected,
        "predicted": predicted,
        "false_negative": expected - tp,
        "false_positive": predicted - tp,
        "precision": tp / predicted if predicted else None,
        "recall": tp / expected if expected else None,
        "f1": 2 * tp / (expected + predicted) if expected + predicted else None,
    }


def extraction_metrics(documents: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    invoices = [d for d in documents if d["type"] == "invoice"]
    core: dict[str, dict[str, Any]] = {}
    for field in CORE_FIELDS:
        compared = 0
        correct = 0
        missing = 0
        for doc in invoices:
            source = doc["source"]
            expected = source["printed_vendor_name"] if field == "vendor_name" else source["number"] if field == "invoice_number" else source[field]
            if expected is None:
                continue
            compared += 1
            predicted = predictions.get(doc["id"])
            actual = field_value(predicted, field) if predicted else None
            if actual is None:
                missing += 1
            elif same_value(expected, actual, field):
                correct += 1
        core[field] = {
            "correct": correct, "expected": compared,
            "missing": missing, "incorrect": compared - correct - missing,
            "exact_match": correct / compared if compared else None,
        }
    lines: dict[str, dict[str, Any]] = {}
    for field in LINE_FIELDS:
        tp = expected_count = predicted_count = 0
        for doc in invoices:
            expected_tokens = line_tokens(doc["source"]["lines"], field)
            actual_tokens = line_tokens(predicted_lines(predictions.get(doc["id"], {})), field)
            tp += sum((expected_tokens & actual_tokens).values())
            expected_count += sum(expected_tokens.values())
            predicted_count += sum(actual_tokens.values())
        lines[field] = metric(tp, expected_count, predicted_count)
    total_tp = sum(value["true_positive"] for value in lines.values())
    total_expected = sum(value["expected"] for value in lines.values())
    total_predicted = sum(value["predicted"] for value in lines.values())
    return {
        "invoices": len(invoices),
        "predicted_invoices": sum(bool(predictions.get(doc["id"], {}).get("fields")) for doc in invoices),
        "core_fields": core,
        "core_micro_exact_match": (
            sum(value["correct"] for value in core.values()) / sum(value["expected"] for value in core.values())
            if sum(value["expected"] for value in core.values()) else None
        ),
        "line_fields": lines,
        "line_micro": metric(total_tp, total_expected, total_predicted),
    }


def finding_metrics(documents: list[dict[str, Any]], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected: set[tuple[str, str]] = set()
    predicted: set[tuple[str, str]] = set()
    unknown: list[dict[str, str]] = []
    clean_negatives = 0
    for doc in documents:
        expected_kinds = {finding["kind"] for finding in doc["expected_findings"]}
        if not expected_kinds:
            clean_negatives += 1
        expected.update((doc["id"], kind) for kind in expected_kinds)
        for kind in findings_for(predictions.get(doc["id"])):
            predicted.add((doc["id"], kind))
            if kind not in FINDING_KINDS:
                unknown.append({"id": doc["id"], "kind": kind})
    tp = expected & predicted
    false_positive = sorted(predicted - expected)
    false_negative = sorted(expected - predicted)
    result = metric(len(tp), len(expected), len(predicted))
    result.update({
        "clean_negative_documents": clean_negatives,
        "false_positive_examples": [{"id": identifier, "kind": kind} for identifier, kind in false_positive[:30]],
        "false_negative_examples": [{"id": identifier, "kind": kind} for identifier, kind in false_negative[:30]],
        "unknown_predicted_kinds": unknown[:30],
        "ambiguous_expected": sum(kind == "ambiguous_vendor_match" for _, kind in expected),
    })
    return result


def evaluate(truth: dict[str, Any], predictions: dict[str, Any] | None) -> dict[str, Any]:
    docs = truth["documents"]
    counts = {
        "documents": len(docs),
        "types": dict(Counter(d["type"] for d in docs)),
        "invoice_lines": sum(len(d["source"]["lines"]) for d in docs if d["type"] == "invoice"),
        "scanned": sum(d["render"]["scanned"] for d in docs),
        "held_out_layouts": sorted({d["layout_id"] for d in docs if d["split"] == "held_out"}),
        "labeled_findings": sum(len(d["expected_findings"]) for d in docs),
    }
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": truth.get("dataset"),
        "seed": truth.get("seed"),
        "reference_date": truth.get("reference_date"),
        "inventory": counts,
        "quality_status": "pending_predictions" if predictions is None else "measured",
        "targets": {"held_out_core_exact_match": 0.95, "held_out_line_f1": 0.90, "finding_precision": 0.90, "finding_recall": 0.90},
    }
    if predictions is None:
        result["limitations"] = ["No application predictions supplied. No extraction or finding accuracy was measured."]
        return result
    indexed = prediction_index(predictions)
    truth_ids = {doc["id"] for doc in docs}
    extras = sorted(set(indexed) - truth_ids)
    if extras:
        raise ValueError(f"Predictions contain {len(extras)} unknown document ids: {extras[:5]}")
    result["prediction_coverage"] = {"documents": len(indexed), "truth_documents": len(docs)}
    if "processing_statuses" in predictions:
        result["processing_statuses"] = predictions["processing_statuses"]
    if "system" in predictions:
        result["prediction_system"] = predictions["system"]
    result["splits"] = {}
    for split in ("development", "held_out", "all"):
        selected = docs if split == "all" else [d for d in docs if d["split"] == split]
        result["splits"][split] = {}
        for medium in ("native", "scanned", "all"):
            group = selected if medium == "all" else [d for d in selected if d["render"]["scanned"] == (medium == "scanned")]
            result["splits"][split][medium] = {
                "extraction": extraction_metrics(group, indexed),
                "findings": finding_metrics(group, indexed),
            }
    held = result["splits"]["held_out"]["all"]["extraction"]
    findings = result["splits"]["all"]["all"]["findings"]
    result["target_check"] = {
        "held_out_core_exact_match": held["core_micro_exact_match"] is not None and held["core_micro_exact_match"] >= 0.95,
        "held_out_line_f1": held["line_micro"]["f1"] is not None and held["line_micro"]["f1"] >= 0.90,
        "finding_precision": findings["precision"] is not None and findings["precision"] >= 0.90,
        "finding_recall": findings["recall"] is not None and findings["recall"] >= 0.90,
    }
    return result


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def markdown_report(result: dict[str, Any], prediction_path: Path | None) -> str:
    inventory = result["inventory"]
    lines = [
        "# InvoiceLens evaluation report", "",
        f"Generated: {result['generated_at_utc']}",
        f"Dataset: {result['dataset']} (seed {result['seed']}, reference date {result['reference_date']})", "",
        "## Dataset inventory", "",
        f"{inventory['documents']} documents; {inventory['types']}; {inventory['invoice_lines']} invoice lines; {inventory['scanned']} scanned documents; held-out layouts {inventory['held_out_layouts']}; {inventory['labeled_findings']} labeled findings.", "",
    ]
    if prediction_path is None:
        lines += ["## Quality measurements", "", "Pending. No application predictions were supplied, so extraction accuracy, line F1, and finding precision/recall have not been measured.", ""]
        return "\n".join(lines)
    lines += [f"Predictions: `{prediction_path}`", "", "## Held-out extraction", "",
              "| Medium | Invoices with predictions / expected | Core field exact match | Line field micro F1 |", "|---|---:|---:|---:|"]
    for medium in ("native", "scanned", "all"):
        item = result["splits"]["held_out"][medium]["extraction"]
        lines.append(f"| {medium} | {item['predicted_invoices']} / {item['invoices']} | {percent(item['core_micro_exact_match'])} | {percent(item['line_micro']['f1'])} ({item['line_micro']['true_positive']} TP; {item['line_micro']['expected']} expected; {item['line_micro']['predicted']} predicted) |")
    if "processing_statuses" in result:
        lines += ["", f"Persisted job statuses: `{result['processing_statuses']}`"]
    lines += ["", "### Per-field denominators (held-out, all media)", "", "| Field | Correct / expected | Missing | Exact match |", "|---|---:|---:|---:|"]
    held = result["splits"]["held_out"]["all"]["extraction"]
    for field, item in held["core_fields"].items():
        lines.append(f"| {field} | {item['correct']} / {item['expected']} | {item['missing']} | {percent(item['exact_match'])} |")
    lines += ["", "| Line field | TP / expected | Predicted | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|---:|"]
    for field, item in held["line_fields"].items():
        lines.append(f"| {field} | {item['true_positive']} / {item['expected']} | {item['predicted']} | {percent(item['precision'])} | {percent(item['recall'])} | {percent(item['f1'])} |")
    finding = result["splits"]["all"]["all"]["findings"]
    lines += ["", "## Findings on all labeled scenarios", "",
              f"Precision {percent(finding['precision'])} ({finding['true_positive']} / {finding['predicted']}); recall {percent(finding['recall'])} ({finding['true_positive']} / {finding['expected']}). False positives {finding['false_positive']}; false negatives {finding['false_negative']}; clean negative documents {finding['clean_negative_documents']}; ambiguous vendor labels {finding['ambiguous_expected']}.", "",
              f"False positive examples: `{finding['false_positive_examples']}`", "",
              f"False negative examples: `{finding['false_negative_examples']}`", "",
              "## Target check", ""]
    for name, passed in result["target_check"].items():
        lines.append(f"- {name}: {'met' if passed else 'not met'}")
    lines += ["", "Matching rules: core strings are trimmed and case-folded; ISO dates are exact; monetary values compare as Decimal. Line fields use a multiset keyed by normalized SKU and value, preserving duplicate rows. Findings require exact document ID and kind. Missing prediction documents count as misses, and unknown finding kinds count as false positives. This synthetic score does not estimate real-customer accuracy.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    truth = load_json(args.truth)
    predictions = load_json(args.predictions) if args.predictions else None
    result = evaluate(truth, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(markdown_report(result, args.predictions) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(args.output), "report": str(args.report), "quality_status": result["quality_status"]}, indent=2))


if __name__ == "__main__":
    main()
