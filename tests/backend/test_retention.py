"""Retention must delete exactly one tenant's old records, files, and graph state."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from invoicelens.db import Base
from invoicelens.models import (
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
    PurchaseOrder,
    ReviewDecision,
    User,
    Workspace,
)
from invoicelens.retention import RetentionError, build_plan, execute_plan
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

OLD = datetime(2020, 1, 1, tzinfo=UTC)
NEW = datetime(2026, 1, 1, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def _checkpoint(path: Path, thread: str) -> None:
    with SqliteSaver.from_conn_string(str(path)) as saver:
        saver.put(
            {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
            {
                "id": "checkpoint-1",
                "ts": OLD.isoformat(),
                "channel_values": {"text": "private"},
            },
            {"source": "input", "step": 1, "writes": {}},
            {},
        )


def _checkpoint_count(path: Path, thread: str) -> int:
    with SqliteSaver.from_conn_string(str(path)) as saver:
        return sum(1 for _ in saver.list({"configurable": {"thread_id": thread}}))


@pytest.fixture
def isolated_retention(tmp_path):
    # pytest's temporary root is redirected to project-local D: by conftest.
    db_path = tmp_path / "retention.db"
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    storage_root = tmp_path / "uploads"
    for name in ("tenant-a", "tenant-b"):
        (storage_root / name).mkdir(parents=True)
    for name, key in (
        ("tenant-a", "old.pdf"),
        ("tenant-a", "export-old.csv"),
        ("tenant-a", "recent.pdf"),
        ("tenant-b", "other.pdf"),
    ):
        (storage_root / name / key).write_bytes(b"private fixture")
    old_id, recent_id, other_id = "a" * 32, "c" * 32, "b" * 32
    with Session(engine) as db:
        db.add_all(
            [
                Workspace(id="tenant-a", name="A", is_demo=False),
                Workspace(id="tenant-b", name="B", is_demo=False),
            ]
        )
        db.add(
            User(
                id="u" * 32,
                workspace_id="tenant-a",
                email="a@example.test",
                password_hash="test",
                role="admin",
            )
        )
        db.flush()
        db.add_all(
            [
                Document(
                    id=old_id,
                    workspace_id="tenant-a",
                    filename="old.pdf",
                    content_type="application/pdf",
                    storage_key="old.pdf",
                    sha256="1" * 64,
                    kind="invoice",
                    created_at=OLD,
                    updated_at=OLD,
                ),
                Document(
                    id=recent_id,
                    workspace_id="tenant-a",
                    filename="recent.pdf",
                    content_type="application/pdf",
                    storage_key="recent.pdf",
                    sha256="2" * 64,
                    kind="purchase_order",
                    created_at=NEW,
                    updated_at=NEW,
                ),
                Document(
                    id=other_id,
                    workspace_id="tenant-b",
                    filename="other.pdf",
                    content_type="application/pdf",
                    storage_key="other.pdf",
                    sha256="3" * 64,
                    kind="invoice",
                    created_at=OLD,
                    updated_at=OLD,
                ),
            ]
        )
        db.flush()
        db.add(
            DocumentPage(
                workspace_id="tenant-a",
                document_id=old_id,
                page_number=1,
                text="private OCR text",
                words=[],
            )
        )
        version = ExtractionVersion(
            workspace_id="tenant-a",
            document_id=old_id,
            version=1,
            data={"private": "text"},
            content_hash="hash",
            source="demo",
            created_at=OLD,
        )
        db.add(version)
        invoice = Invoice(workspace_id="tenant-a", document_id=old_id)
        po = PurchaseOrder(
            workspace_id="tenant-a", document_id=recent_id, po_number="PO-RECENT"
        )
        job = Job(
            workspace_id="tenant-a",
            document_id=old_id,
            status="complete",
            created_at=OLD,
            updated_at=OLD,
        )
        finding = Finding(
            workspace_id="tenant-a",
            document_id=old_id,
            extraction_version=1,
            code="TEST",
            severity="warning",
            message="private",
        )
        db.add_all([invoice, po, job, finding])
        db.flush()
        db.add_all(
            [
                ExtractedFieldEvidence(
                    workspace_id="tenant-a",
                    extraction_version_id=version.id,
                    field_key="vendor",
                    raw="private",
                    value="private",
                    source="demo",
                ),
                InvoiceLine(
                    workspace_id="tenant-a",
                    invoice_id=invoice.id,
                    position=1,
                    description="private line",
                ),
                MatchProposal(
                    workspace_id="tenant-a",
                    document_id=old_id,
                    extraction_version=1,
                    po_id=po.id,
                    score=1,
                    details={},
                ),
                ReviewDecision(
                    workspace_id="tenant-a",
                    document_id=old_id,
                    extraction_version=1,
                    finding_id=finding.id,
                    user_id="u" * 32,
                    action="accept",
                    created_at=OLD,
                ),
                ExportJob(
                    workspace_id="tenant-a",
                    document_id=old_id,
                    version=1,
                    format="csv",
                    storage_key="export-old.csv",
                    sha256="4" * 64,
                    created_at=OLD,
                ),
                ActionLedger(
                    workspace_id="tenant-a",
                    document_id=old_id,
                    action_key="export:old",
                    kind="export",
                    created_at=OLD,
                ),
                JobEvent(
                    workspace_id="tenant-a",
                    job_id=job.id,
                    type="complete",
                    message="private event",
                    created_at=OLD,
                ),
            ]
        )
        db.commit()
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    _checkpoint(checkpoint_path, f"tenant-a:{old_id}")
    _checkpoint(checkpoint_path, f"tenant-b:{other_id}")
    yield engine, url, storage_root, checkpoint_path, old_id, recent_id, other_id
    engine.dispose()


def test_dry_run_then_workspace_scoped_apply(isolated_retention):
    engine, url, root, checkpoints, old_id, recent_id, other_id = isolated_retention
    with Session(engine) as db:
        plan = build_plan(db, "tenant-a", date(2025, 1, 1), root)
    assert plan["document_ids"] == [old_id]
    assert plan["storage_keys"] == ["export-old.csv", "old.pdf"]
    assert (root / "tenant-a" / "old.pdf").exists()  # Dry-run wrote nothing.
    assert _checkpoint_count(checkpoints, f"tenant-a:{old_id}") == 1

    journal = root.parent / "retention-journals" / "tenant-a-fixture.json"
    result = execute_plan(engine, plan, root, url, checkpoints, journal)
    assert result["state"] == "complete"
    assert not (root / "tenant-a" / "old.pdf").exists()
    assert not (root / "tenant-a" / "export-old.csv").exists()
    assert (root / "tenant-a" / "recent.pdf").exists()
    assert (root / "tenant-b" / "other.pdf").exists()
    assert _checkpoint_count(checkpoints, f"tenant-a:{old_id}") == 0
    assert _checkpoint_count(checkpoints, f"tenant-b:{other_id}") == 1
    with Session(engine) as db:
        assert db.get(Document, old_id) is None
        assert db.get(Document, recent_id) is not None
        assert db.get(Document, other_id) is not None
        assert not db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == old_id)
        ).all()
        assert not db.scalars(
            select(ExportJob).where(ExportJob.document_id == old_id)
        ).all()
        assert not db.scalars(
            select(ReviewDecision).where(ReviewDecision.document_id == old_id)
        ).all()
        assert not db.scalars(select(Job).where(Job.document_id == old_id)).all()
    assert (
        execute_plan(engine, plan, root, url, checkpoints, journal, resume=True)[
            "state"
        ]
        == "complete"
    )


def test_processing_job_blocks_apply(isolated_retention):
    engine, url, root, checkpoints, old_id, _, _ = isolated_retention
    with Session(engine) as db:
        plan = build_plan(db, "tenant-a", date(2025, 1, 1), root)
        job = db.scalar(select(Job).where(Job.document_id == old_id))
        job.status = "processing"
        db.commit()
    journal = root.parent / "retention-journals" / "tenant-a-blocked.json"
    with pytest.raises(RetentionError, match="processing jobs"):
        execute_plan(engine, plan, root, url, checkpoints, journal)
    assert (root / "tenant-a" / "old.pdf").exists()
    with Session(engine) as db:
        assert db.get(Document, old_id) is not None


def test_unreviewed_document_table_fails_closed(isolated_retention):
    engine, _, root, _, _, _, _ = isolated_retention
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE new_private_rows (id TEXT, workspace_id TEXT, document_id TEXT)"
            )
        )
    with (
        Session(engine) as db,
        pytest.raises(RetentionError, match="Unreviewed workspace table"),
    ):
        build_plan(db, "tenant-a", date(2025, 1, 1), root)


def test_purchase_order_blockers_reach_fixed_point(isolated_retention):
    engine, _, root, _, old_id, recent_id, _ = isolated_retention
    outer_id, inner_id = "z" * 32, "d" * 32
    (root / "tenant-a" / "po-outer.pdf").write_bytes(b"outer")
    (root / "tenant-a" / "po-inner.pdf").write_bytes(b"inner")
    with Session(engine) as db:
        db.add_all(
            [
                Document(
                    id=outer_id,
                    workspace_id="tenant-a",
                    filename="po-outer.pdf",
                    content_type="application/pdf",
                    storage_key="po-outer.pdf",
                    sha256="5" * 64,
                    kind="purchase_order",
                    created_at=OLD,
                    updated_at=OLD,
                ),
                Document(
                    id=inner_id,
                    workspace_id="tenant-a",
                    filename="po-inner.pdf",
                    content_type="application/pdf",
                    storage_key="po-inner.pdf",
                    sha256="6" * 64,
                    kind="purchase_order",
                    created_at=OLD,
                    updated_at=OLD,
                ),
            ]
        )
        db.flush()
        outer_po = PurchaseOrder(
            workspace_id="tenant-a", document_id=outer_id, po_number="PO-OUTER"
        )
        inner_po = PurchaseOrder(
            workspace_id="tenant-a", document_id=inner_id, po_number="PO-INNER"
        )
        db.add_all([outer_po, inner_po])
        db.flush()
        # A retained document references the outer PO. The outer PO in turn has
        # a proposal referencing the inner PO. The inner PO sorts first by ID.
        db.add_all(
            [
                MatchProposal(
                    workspace_id="tenant-a",
                    document_id=recent_id,
                    extraction_version=1,
                    po_id=outer_po.id,
                    score=1,
                    details={},
                ),
                MatchProposal(
                    workspace_id="tenant-a",
                    document_id=outer_id,
                    extraction_version=1,
                    po_id=inner_po.id,
                    score=1,
                    details={},
                ),
            ]
        )
        db.commit()
    with Session(engine) as db:
        plan = build_plan(db, "tenant-a", date(2025, 1, 1), root)
    assert plan["document_ids"] == [old_id]
    assert plan["blocked_purchase_order_ids"] == [inner_id, outer_id]
