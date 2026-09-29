"""Load rendered synthetic documents through the ordinary upload and job pipeline."""

import argparse
import json
from pathlib import Path

from sqlalchemy import delete

from .config import get_settings
from .db import SessionLocal, create_schema
from .models import (
    ActionLedger,
    Document,
    DocumentPage,
    ExportJob,
    ExtractedFieldEvidence,
    ExtractionVersion,
    Finding,
    Invoice,
    InvoiceLine,
    Job,
    JobEvent,
    MatchProposal,
    POLine,
    PurchaseOrder,
    ReviewDecision,
    Vendor,
    Workspace,
)
from .security import seed_demo_users
from .service import upload_document
from .workflow import run_job


def reset_demo(db, workspace_ids: set[str]) -> None:
    if get_settings().mode != "DEMO":
        raise ValueError("Demo reset is available only in DEMO mode")
    if not workspace_ids or any(
        not workspace_id.startswith("harbor-demo-") for workspace_id in workspace_ids
    ):
        raise ValueError("Reset is limited to explicit harbor-demo workspaces")
    for workspace_id in workspace_ids:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None or not workspace.is_demo:
            raise ValueError(f"Workspace {workspace_id} is not a demo workspace")
    for model in (
        ExtractedFieldEvidence,
        InvoiceLine,
        POLine,
        MatchProposal,
        Finding,
        ReviewDecision,
        ExportJob,
        ActionLedger,
        JobEvent,
        Invoice,
        PurchaseOrder,
        ExtractionVersion,
        DocumentPage,
        Job,
        Document,
        Vendor,
    ):
        db.execute(delete(model).where(model.workspace_id.in_(workspace_ids)))
    db.commit()


def load_manifest(
    path: Path,
    *,
    reset: bool = False,
    process_first: int = 0,
    only_types: set[str] | None = None,
) -> dict:
    path = path.resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("dataset") != "Synthetic demo dataset"
        or manifest.get("schema_version") != "1.0"
    ):
        raise ValueError("Expected synthetic InvoiceLens manifest v1.0")
    entries = manifest.get("documents", [])
    if not isinstance(entries, list):
        raise ValueError("Manifest documents must be a list")
    create_schema()
    with SessionLocal() as db:
        seed_demo_users(db)
        workspace_ids = {item["workspace"] for item in entries}
        if reset:
            reset_demo(db, workspace_ids)
        accepted = deduplicated = 0
        first_jobs = []
        for item in entries:
            if only_types is not None and item.get("type") not in only_types:
                continue
            workspace_id = item["workspace"]
            if workspace_id not in {"harbor-demo-a", "harbor-demo-b"}:
                raise ValueError(f"Manifest workspace {workspace_id} is outside demo namespaces")
            source = (path.parent / item["path"]).resolve()
            if not source.is_relative_to(path.parent):
                raise ValueError("Manifest path escapes its directory")
            document, job, duplicate = upload_document(
                db, workspace_id, source.name, source.read_bytes()
            )
            accepted += 1
            deduplicated += int(duplicate)
            if not duplicate and len(first_jobs) < process_first:
                first_jobs.append(job.id)
    for job_id in first_jobs:
        run_job(job_id)
    return {"accepted": accepted, "deduplicated": deduplicated, "processed_inline": len(first_jobs)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--reset", action="store_true", help="Clear only demo workspace records before loading"
    )
    parser.add_argument(
        "--process-first",
        type=int,
        default=0,
        help="Process this many queued documents synchronously",
    )
    parser.add_argument(
        "--only-type",
        action="append",
        choices=("invoice", "purchase_order", "credit_note"),
        help="Seed only the specified document type; repeat to include several types",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            load_manifest(
                args.manifest,
                reset=args.reset,
                process_first=args.process_first,
                only_types=set(args.only_type) if args.only_type else None,
            )
        )
    )


if __name__ == "__main__":
    main()
