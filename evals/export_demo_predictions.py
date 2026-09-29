"""Export actual persisted DEMO workflow outputs for blind synthetic evaluation.

Inputs are the public manifest and a separate DEMO SQLite database. This
script never opens ``evals/data`` or imports generator scenario truth.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "generated" / "invoicelens" / "manifest.json"
DEFAULT_DATABASE = ROOT / "evals" / "results" / "invoicelens-eval.db"
DEFAULT_OUTPUT = ROOT / "evals" / "results" / "demo_predictions.json"

FINDING_CODES = {
    "DUPLICATE_INVOICE": "duplicate_invoice",
    "UNIT_PRICE_MISMATCH": "unit_price_mismatch",
    "PO_NOT_FOUND": "po_missing",
    "MISSING_PO": "po_missing",
    "QUANTITY_OVER_PO": "quantity_mismatch",
    "TOTAL_MISMATCH": "total_inconsistent",
    "AMBIGUOUS_VENDOR": "ambiguous_vendor_match",
}


def load_predictions(manifest_path: Path, database_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset") != "Synthetic demo dataset" or manifest.get("schema_version") != "1.0":
        raise ValueError("Expected public synthetic manifest v1.0")
    if not database_path.is_file():
        raise FileNotFoundError(f"DEMO evaluation database not found: {database_path}")
    db = sqlite3.connect(str(database_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    predictions = []
    status_counts: Counter[str] = Counter()
    try:
        for item in manifest["documents"]:
            filename = Path(item["path"]).name
            rows = db.execute(
                "SELECT id, version, status FROM documents WHERE workspace_id=? AND filename=? ORDER BY created_at DESC",
                (item["workspace"], filename),
            ).fetchall()
            if len(rows) > 1:
                raise ValueError(f"Ambiguous database filename in workspace: {item['workspace']}/{filename}")
            prediction: dict = {"id": item["id"], "fields": {}, "lines": [], "findings": []}
            if not rows:
                prediction["processing_status"] = "not_ingested"
                status_counts["not_ingested"] += 1
                predictions.append(prediction)
                continue
            document = rows[0]
            job = db.execute(
                "SELECT status, error FROM jobs WHERE document_id=? ORDER BY created_at DESC LIMIT 1",
                (document["id"],),
            ).fetchone()
            processing_status = job["status"] if job else document["status"]
            prediction["processing_status"] = processing_status
            if job and job["error"]:
                prediction["processing_error"] = job["error"][:240]
            status_counts[processing_status] += 1
            if document["version"]:
                version = db.execute(
                    "SELECT data FROM extraction_versions WHERE document_id=? AND version=?",
                    (document["id"], document["version"]),
                ).fetchone()
                if version:
                    data = json.loads(version["data"])
                    fields = data.get("fields", {})
                    prediction["fields"] = {
                        "vendor_name": fields.get("vendor", {}).get("value"),
                        "invoice_number": fields.get("number", {}).get("value"),
                        "date": fields.get("date", {}).get("value"),
                        "currency": fields.get("currency", {}).get("value"),
                        "total": fields.get("total", {}).get("value"),
                    }
                    prediction["lines"] = [
                        {
                            "sku": line.get("sku"),
                            "description": line.get("description"),
                            "quantity": line.get("quantity"),
                            "unit": line.get("unit"),
                            "unit_price": line.get("unit_price"),
                            "line_amount": line.get("amount"),
                        }
                        for line in data.get("lines", [])
                    ]
                    codes = db.execute(
                        "SELECT DISTINCT code FROM findings WHERE document_id=? AND extraction_version=?",
                        (document["id"], document["version"]),
                    ).fetchall()
                    prediction["findings"] = [
                        {"kind": FINDING_CODES.get(row["code"], f"unmapped:{row['code'].lower()}")}
                        for row in codes
                    ]
            predictions.append(prediction)
    finally:
        db.close()
    return {
        "schema_version": "1.0",
        "system": "InvoiceLens DEMO persisted workflow outputs",
        "source_manifest": str(manifest_path),
        "processing_statuses": dict(status_counts),
        "documents": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--status-only", action="store_true", help="Print current job status counts without writing predictions")
    args = parser.parse_args()
    predictions = load_predictions(args.manifest.resolve(), args.database.resolve())
    if args.status_only:
        print(json.dumps({"processing_statuses": predictions["processing_statuses"]}, indent=2))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(predictions, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "processing_statuses": predictions["processing_statuses"]}, indent=2))


if __name__ == "__main__":
    main()
