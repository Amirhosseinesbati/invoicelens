"""Offline, workspace-scoped retention maintenance for stored documents.

Dry-run is the default. Applying a plan requires a stopped API/worker and an
explicit confirmation. A durable journal permits retrying file/checkpoint
cleanup after the business-database transaction has committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import create_engine, delete, inspect, select
from sqlalchemy.orm import Session

from .config import get_settings
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
    Workspace,
)


class RetentionError(ValueError):
    """Fail closed rather than risk a partial or cross-workspace purge."""


DOMAIN_TABLES = {
    model.__tablename__
    for model in (
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
        ActionLedger,
    )
}
KNOWN_UNSCOPED_TABLES = {
    "workspaces",
    "users",
    "vendors",
    "alembic_version",
    "checkpoints",
    "writes",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}
WORKSPACE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
STORAGE_KEY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\Z")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _cutoff(before: date) -> datetime:
    return datetime(before.year, before.month, before.day, tzinfo=UTC)


def _check_schema(engine) -> None:
    """Refuse schemas with unreviewed document relations or workspace tables."""
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        if table_name in DOMAIN_TABLES or table_name in KNOWN_UNSCOPED_TABLES:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "workspace_id" in columns or "document_id" in columns:
            raise RetentionError(f"Unreviewed workspace table: {table_name}")
        for fk in inspector.get_foreign_keys(table_name):
            if fk.get("referred_table") in DOMAIN_TABLES:
                raise RetentionError(f"Unreviewed dependent table: {table_name}")


def _workspace_path(storage_root: Path, workspace_id: str) -> Path:
    if not WORKSPACE_PATTERN.fullmatch(workspace_id):
        raise RetentionError("Invalid workspace identifier")
    root = storage_root.resolve()
    path = root / workspace_id
    if path.is_symlink() or path.resolve() != path:
        raise RetentionError("Workspace storage path is a symlink or escapes storage root")
    return path


def _file_path(storage_root: Path, workspace_id: str, key: str) -> Path:
    if not STORAGE_KEY_PATTERN.fullmatch(key):
        raise RetentionError(f"Unsafe storage key: {key!r}")
    path = _workspace_path(storage_root, workspace_id) / key
    if path.is_symlink() or path.resolve() != path:
        raise RetentionError(f"Stored file is a symlink or escapes workspace: {key}")
    if path.exists() and not path.is_file():
        raise RetentionError(f"Storage key is not a regular file: {key}")
    return path


def _latest_activity(db: Session, document: Document) -> datetime:
    values = [document.created_at, document.updated_at, document.approved_at]
    for model, column in (
        (ExportJob, ExportJob.created_at),
        (ExtractionVersion, ExtractionVersion.created_at),
        (ReviewDecision, ReviewDecision.created_at),
        (ActionLedger, ActionLedger.created_at),
        (Job, Job.updated_at),
        (JobEvent, JobEvent.created_at),
    ):
        if model is JobEvent:
            job_ids = select(Job.id).where(
                Job.workspace_id == document.workspace_id, Job.document_id == document.id
            )
            statement = select(column).where(
                JobEvent.workspace_id == document.workspace_id, JobEvent.job_id.in_(job_ids)
            )
        else:
            statement = select(column).where(
                model.workspace_id == document.workspace_id,
                model.document_id == document.id,
            )
        values.extend(db.scalars(statement).all())
    dated = [converted for value in values if (converted := _utc(value)) is not None]
    if not dated:
        raise RetentionError("Document has no activity timestamp")
    return max(dated)


def _processing_jobs(db: Session, workspace_id: str) -> list[str]:
    return list(
        db.scalars(
            select(Job.id).where(Job.workspace_id == workspace_id, Job.status == "processing")
        ).all()
    )


def build_plan(db: Session, workspace_id: str, before: date, storage_root: Path) -> dict:
    """Select only inactive old documents in one workspace, without writing."""
    _workspace_path(storage_root, workspace_id)
    if db.get(Workspace, workspace_id) is None:
        raise RetentionError(f"Workspace does not exist: {workspace_id}")
    _check_schema(db.get_bind())
    cutoff = _cutoff(before)
    documents = db.scalars(
        select(Document).where(Document.workspace_id == workspace_id).order_by(Document.id)
    ).all()
    candidates = [doc for doc in documents if _latest_activity(db, doc) < cutoff]
    selected = {doc.id: doc for doc in candidates}
    blocked_po: list[str] = []
    # Removing one PO can leave another PO referenced by a newly retained row.
    # Recompute until no selected PO is referenced from outside the selection.
    while True:
        newly_blocked = []
        for doc in selected.values():
            po = db.scalar(
                select(PurchaseOrder).where(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.document_id == doc.id,
                )
            )
            if po and db.scalar(
                select(MatchProposal.id).where(
                    MatchProposal.po_id == po.id,
                    MatchProposal.document_id.not_in(selected),
                )
            ):
                newly_blocked.append(doc.id)
        if not newly_blocked:
            break
        for identifier in newly_blocked:
            selected.pop(identifier)
        blocked_po.extend(newly_blocked)
    document_ids = sorted(selected)
    keys = {doc.storage_key for doc in selected.values()}
    if document_ids:
        keys.update(
            db.scalars(
                select(ExportJob.storage_key).where(
                    ExportJob.workspace_id == workspace_id,
                    ExportJob.document_id.in_(document_ids),
                )
            ).all()
        )
    for key in keys:
        _file_path(storage_root, workspace_id, key)
        retained_doc = db.scalar(
            select(Document.id).where(
                Document.workspace_id == workspace_id,
                Document.storage_key == key,
                Document.id.not_in(document_ids),
            )
        )
        retained_export = db.scalar(
            select(ExportJob.id).where(
                ExportJob.workspace_id == workspace_id,
                ExportJob.storage_key == key,
                ExportJob.document_id.not_in(document_ids),
            )
        )
        if retained_doc or retained_export:
            raise RetentionError(f"Stored file is also referenced by retained data: {key}")
    return {
        "schema_version": 1,
        "workspace_id": workspace_id,
        "before": before.isoformat(),
        "document_ids": document_ids,
        "storage_keys": sorted(keys),
        "blocked_purchase_order_ids": sorted(blocked_po),
        "recent_or_active_document_count": len(documents) - len(candidates),
        "processing_job_count": len(_processing_jobs(db, workspace_id)),
        "storage_root": str(storage_root.resolve()),
    }


def _verify_plan(db: Session, plan: dict) -> None:
    workspace_id = plan["workspace_id"]
    cutoff = _cutoff(date.fromisoformat(plan["before"]))
    if _processing_jobs(db, workspace_id):
        raise RetentionError("Workspace has processing jobs; stop workers and resolve them first")
    for identifier in plan["document_ids"]:
        doc = db.get(Document, identifier)
        if doc is None:
            continue  # A retry after a committed database deletion.
        if doc.workspace_id != workspace_id or _latest_activity(db, doc) >= cutoff:
            raise RetentionError(f"Document no longer qualifies for retention: {identifier}")


def _delete_records(db: Session, plan: dict) -> None:
    workspace_id = plan["workspace_id"]
    with db.begin():
        _verify_plan(db, plan)
        for document_id in plan["document_ids"]:
            extraction_ids = db.scalars(
                select(ExtractionVersion.id).where(
                    ExtractionVersion.workspace_id == workspace_id,
                    ExtractionVersion.document_id == document_id,
                )
            ).all()
            invoice_ids = db.scalars(
                select(Invoice.id).where(
                    Invoice.workspace_id == workspace_id,
                    Invoice.document_id == document_id,
                )
            ).all()
            po_ids = db.scalars(
                select(PurchaseOrder.id).where(
                    PurchaseOrder.workspace_id == workspace_id,
                    PurchaseOrder.document_id == document_id,
                )
            ).all()
            job_ids = db.scalars(
                select(Job.id).where(
                    Job.workspace_id == workspace_id,
                    Job.document_id == document_id,
                )
            ).all()
            for model, fk, ids in (
                (
                    ExtractedFieldEvidence,
                    ExtractedFieldEvidence.extraction_version_id,
                    extraction_ids,
                ),
                (InvoiceLine, InvoiceLine.invoice_id, invoice_ids),
                (POLine, POLine.po_id, po_ids),
                (JobEvent, JobEvent.job_id, job_ids),
            ):
                if ids:
                    db.execute(delete(model).where(model.workspace_id == workspace_id, fk.in_(ids)))
            for model in (
                ReviewDecision,
                MatchProposal,
                Finding,
                ExportJob,
                ActionLedger,
                Invoice,
                PurchaseOrder,
                ExtractionVersion,
                DocumentPage,
                Job,
            ):
                db.execute(
                    delete(model).where(
                        model.workspace_id == workspace_id, model.document_id == document_id
                    )
                )
            db.execute(
                delete(Document).where(
                    Document.workspace_id == workspace_id, Document.id == document_id
                )
            )


def _delete_checkpoints(plan: dict, database_url: str, checkpoint_path: Path) -> None:
    threads = [f"{plan['workspace_id']}:{identifier}" for identifier in plan["document_ids"]]
    if not threads:
        return
    if database_url.startswith("postgresql"):
        pg_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        with PostgresSaver.from_conn_string(pg_url) as saver:
            for thread_id in threads:
                saver.delete_thread(thread_id)
    elif database_url.startswith("sqlite"):
        if checkpoint_path.exists():
            with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
                for thread_id in threads:
                    saver.delete_thread(thread_id)
    else:
        raise RetentionError("Unsupported checkpoint database")


def _delete_files(plan: dict, storage_root: Path, engine) -> None:
    workspace_id = plan["workspace_id"]
    with Session(engine) as db:
        for key in plan["storage_keys"]:
            retained = db.scalar(
                select(Document.id).where(
                    Document.workspace_id == workspace_id, Document.storage_key == key
                )
            ) or db.scalar(
                select(ExportJob.id).where(
                    ExportJob.workspace_id == workspace_id, ExportJob.storage_key == key
                )
            )
            if retained:
                raise RetentionError(f"File still has a database reference: {key}")
            _file_path(storage_root, workspace_id, key).unlink(missing_ok=True)


def _journal_dir(storage_root: Path) -> Path:
    return storage_root.resolve().parent / "retention-journals"


def _write_journal(path: Path, journal: dict, *, create: bool = False) -> None:
    payload = json.dumps(journal, indent=2, sort_keys=True) + "\n"
    if create:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)


def execute_plan(
    engine,
    plan: dict,
    storage_root: Path,
    database_url: str,
    checkpoint_path: Path,
    journal_path: Path,
    *,
    resume: bool = False,
) -> dict:
    """Apply or resume an exact plan. Every phase is idempotent."""
    _check_schema(engine)
    if plan["storage_root"] != str(storage_root.resolve()):
        raise RetentionError("Storage root differs from the plan")
    if journal_path.resolve().parent != _journal_dir(storage_root).resolve():
        raise RetentionError("Journal must stay in the configured retention-journals directory")
    expected_fingerprint = hashlib.sha256(database_url.encode()).hexdigest()
    if resume:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if (
            journal.get("plan") != plan
            or journal.get("database_fingerprint") != expected_fingerprint
        ):
            raise RetentionError("Journal does not match this plan or database")
    else:
        if not plan["document_ids"]:
            return {"state": "nothing_to_delete", "journal": None}
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal = {"plan": plan, "database_fingerprint": expected_fingerprint, "state": "planned"}
        _write_journal(journal_path, journal, create=True)
    for key in plan["storage_keys"]:
        _file_path(storage_root, plan["workspace_id"], key)
    states = ("planned", "database_deleted", "checkpoints_deleted", "complete")
    if journal["state"] not in states:
        raise RetentionError("Unrecognized journal state")
    if journal["state"] == "planned":
        with Session(engine) as db:
            _delete_records(db, plan)
        journal["state"] = "database_deleted"
        _write_journal(journal_path, journal)
    if journal["state"] == "database_deleted":
        _delete_checkpoints(plan, database_url, checkpoint_path)
        journal["state"] = "checkpoints_deleted"
        _write_journal(journal_path, journal)
    if journal["state"] == "checkpoints_deleted":
        _delete_files(plan, storage_root, engine)
        journal["state"] = "complete"
        _write_journal(journal_path, journal)
    return {"state": journal["state"], "journal": str(journal_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Exact workspace ID")
    parser.add_argument(
        "--before", type=date.fromisoformat, help="UTC date; keep activity on or after this date"
    )
    parser.add_argument("--apply", action="store_true", help="Perform the planned deletion")
    parser.add_argument(
        "--offline-confirmed", action="store_true", help="Confirm API and workers are stopped"
    )
    parser.add_argument(
        "--resume-journal", type=Path, help="Finish an interrupted deletion journal"
    )
    args = parser.parse_args()
    if not WORKSPACE_PATTERN.fullmatch(args.workspace):
        parser.error("Invalid workspace identifier")
    if args.resume_journal and args.before:
        parser.error("Use either --before or --resume-journal")
    if not args.resume_journal and not args.before:
        parser.error("--before is required for a new plan")
    if args.apply and not args.offline_confirmed:
        parser.error("--apply requires --offline-confirmed after stopping the API and workers")
    settings = get_settings()
    database_url = settings.database_url
    if database_url.startswith("sqlite:///"):
        database_file = Path(database_url.removeprefix("sqlite:///"))
        if not database_file.is_file():
            parser.error(f"Database file does not exist: {database_file}")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        if args.resume_journal:
            path = args.resume_journal.resolve()
            if path.parent != _journal_dir(settings.storage_root).resolve():
                parser.error("Journal path is outside the configured retention-journals directory")
            journal = json.loads(path.read_text(encoding="utf-8"))
            plan = journal["plan"]
            if plan["workspace_id"] != args.workspace:
                parser.error("Journal workspace does not match --workspace")
            if not args.apply:
                print(json.dumps({"plan": plan, "state": journal["state"]}, indent=2))
                return
            result = execute_plan(
                engine,
                plan,
                settings.storage_root,
                database_url,
                settings.checkpoint_path,
                path,
                resume=True,
            )
        else:
            with Session(engine) as db:
                plan = build_plan(db, args.workspace, args.before, settings.storage_root)
            if not args.apply:
                print(json.dumps({"dry_run": True, "plan": plan}, indent=2))
                return
            journal_path = (
                _journal_dir(settings.storage_root) / f"{args.workspace}-{uuid4().hex}.json"
            )
            result = execute_plan(
                engine,
                plan,
                settings.storage_root,
                database_url,
                settings.checkpoint_path,
                journal_path,
            )
        print(json.dumps({"dry_run": False, "plan": plan, "result": result}, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
