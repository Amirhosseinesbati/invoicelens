"""The prediction exporter maps persisted workflow rows, never source truth."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS))

from export_demo_predictions import load_predictions  # noqa: E402


class PredictionExporterTests(unittest.TestCase):
    def test_maps_actual_field_line_and_finding_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.0", "dataset": "Synthetic demo dataset",
                "documents": [{"id": "INV-001", "workspace": "harbor-demo-a", "path": "documents/INV-001.pdf"}],
            }), encoding="utf-8")
            database = root / "eval.db"
            db = sqlite3.connect(database)
            db.executescript("""
                CREATE TABLE documents (id TEXT, workspace_id TEXT, filename TEXT, version INTEGER, status TEXT, created_at TEXT);
                CREATE TABLE jobs (document_id TEXT, status TEXT, error TEXT, created_at TEXT);
                CREATE TABLE extraction_versions (document_id TEXT, version INTEGER, data TEXT);
                CREATE TABLE findings (document_id TEXT, extraction_version INTEGER, code TEXT);
            """)
            db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)", ("db-1", "harbor-demo-a", "INV-001.pdf", 1, "needs_review", "2026-09-27"))
            db.execute("INSERT INTO jobs VALUES (?,?,?,?)", ("db-1", "complete", None, "2026-09-27"))
            db.execute("INSERT INTO extraction_versions VALUES (?,?,?)", ("db-1", 1, json.dumps({
                "fields": {"vendor": {"value": "Alpha"}, "number": {"value": "A-1"},
                           "date": {"value": "2026-09-27"}, "currency": {"value": "USD"},
                           "total": {"value": "12.00"}},
                "lines": [{"sku": "SKU-A", "description": "Bolt", "quantity": "2", "unit": "ea", "unit_price": "6.00", "amount": "12.00"}],
            })))
            db.execute("INSERT INTO findings VALUES (?,?,?)", ("db-1", 1, "UNIT_PRICE_MISMATCH"))
            db.commit()
            db.close()
            exported = load_predictions(manifest, database)
            self.assertEqual(exported["processing_statuses"], {"complete": 1})
            item = exported["documents"][0]
            self.assertEqual(item["fields"]["vendor_name"], "Alpha")
            self.assertEqual(item["lines"][0]["line_amount"], "12.00")
            self.assertEqual(item["findings"], [{"kind": "unit_price_mismatch"}])


if __name__ == "__main__":
    unittest.main()
