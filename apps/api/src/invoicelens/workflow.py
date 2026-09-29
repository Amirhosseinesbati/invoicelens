import json
import logging
from contextlib import contextmanager
from datetime import timedelta
from threading import Event, Thread
from typing import Any, TypedDict, cast

from fastapi import HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import func, or_, select, update

from .config import get_settings
from .connected_pages import ConnectedPageError
from .db import SessionLocal
from .extraction import PageContent, adapter, attach_field_boxes, iter_pages, page_count
from .models import Document, DocumentPage, Finding, Job, User, Vendor, utcnow
from .service import (
    add_event,
    approve_document,
    normalize_version,
    persist_extraction,
    refresh_findings,
)
from .storage import storage_path

log = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    workspace_id: str
    document_id: str
    job_id: str
    version: int
    kind: str
    finding_count: int
    approved: bool
    actor_id: str


class JobCancelled(Exception):
    pass


def _rows(state: WorkflowState):
    with SessionLocal() as db:
        document = db.scalar(
            select(Document).where(
                Document.id == state["document_id"], Document.workspace_id == state["workspace_id"]
            )
        )
        job = db.scalar(
            select(Job).where(Job.id == state["job_id"], Job.workspace_id == state["workspace_id"])
        )
        if not document or not job:
            raise ValueError("Workflow resource no longer exists in workspace")
        if job.status == "cancelled":
            raise JobCancelled()
        yield db, document, job


def ingest(state: WorkflowState) -> dict:
    for db, document, job in _rows(state):
        content = storage_path(document.workspace_id, document.storage_key).read_bytes()
        total_pages = page_count(content, document.content_type)
        job.total_pages = total_pages
        db.commit()
        for page in iter_pages(content, document.content_type):
            db.refresh(job)
            if job.status == "cancelled":
                raise JobCancelled()
            if db.scalar(
                select(DocumentPage).where(
                    DocumentPage.document_id == document.id, DocumentPage.page_number == page.number
                )
            ):
                continue
            db.add(
                DocumentPage(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    page_number=page.number,
                    text=page.text,
                    source_type=page.source_type,
                    width=page.width,
                    height=page.height,
                    words=page.words,
                )
            )
            job.current_page = page.number
            job.progress = min(30, round(30 * page.number / total_pages))
            db.commit()
            add_event(db, job, "page", f"Read page {page.number} of {total_pages}")
        return {}
    raise AssertionError("Workflow resource iterator must yield or raise")


def classify(state: WorkflowState) -> dict:
    for db, document, job in _rows(state):
        if document.kind != "unknown":
            return {"kind": document.kind}
        text = " ".join(page.text[:500] for page in document.pages[:2]).lower()
        document.kind = (
            "credit_note"
            if "credit note" in text
            else "purchase_order"
            if "purchase order" in text and "invoice" not in text
            else "invoice"
            if "invoice" in text
            else "unknown"
        )
        job.progress = 35
        db.commit()
        add_event(db, job, "classified", f"Classified as {document.kind}")
        return {"kind": document.kind}
    raise AssertionError("Workflow resource iterator must yield or raise")


def extract(state: WorkflowState) -> dict:
    for db, document, job in _rows(state):
        if document.version:
            return {"version": document.version}
        pages = [
            PageContent(
                p.page_number, p.text, p.source_type, float(p.width), float(p.height), p.words
            )
            for p in document.pages
        ]
        content = storage_path(document.workspace_id, document.storage_key).read_bytes()
        extractor = adapter()
        extracted = extractor.extract(pages, content, document.content_type)
        field_pages = getattr(extractor, "last_field_pages", None)
        line_pages = getattr(extractor, "last_line_pages", None)
        attach_field_boxes(
            pages, content, document.content_type, extracted, field_pages, line_pages
        )
        persist_extraction(
            db,
            document,
            extracted,
            pages,
            "model" if get_settings().mode == "CONNECTED" else "deterministic",
            field_pages,
            line_pages,
        )
        job.progress = 65
        db.commit()
        add_event(db, job, "extracted", "Structured fields extracted with source evidence")
        usage = getattr(extractor, "last_usage", None)
        if usage:
            add_event(
                db,
                job,
                "model_usage",
                "prompt={prompt_version} input_tokens={input_tokens} output_tokens={output_tokens} "
                "cost_status={cost_status}".format(**usage),
            )
        return {"version": document.version, "kind": document.kind}
    raise AssertionError("Workflow resource iterator must yield or raise")


def normalize(state: WorkflowState) -> dict:
    for db, document, job in _rows(state):
        normalize_version(db, document)
        job.progress = 75
        db.commit()
        add_event(db, job, "normalized", "Dates and amounts normalized")
        return {}
    raise AssertionError("Workflow resource iterator must yield or raise")


def validate(state: WorkflowState) -> dict:
    for db, document, job in _rows(state):
        # Arithmetic and PO matching are deterministic and rerun after each correction.
        refresh_findings(db, document)
        if document.kind == "purchase_order" and document.po_number:
            affected = db.scalars(
                select(Document).where(
                    Document.workspace_id == document.workspace_id,
                    Document.po_number == document.po_number,
                    Document.kind.in_(["invoice", "credit_note"]),
                )
            ).all()
            for invoice in affected:
                refresh_findings(db, invoice)
        if document.vendor_id:
            current_vendor = db.get(Vendor, document.vendor_id)
            if current_vendor:
                vendors = db.scalars(
                    select(Vendor).where(Vendor.workspace_id == document.workspace_id)
                ).all()
                alias_ids = [
                    vendor.id
                    for vendor in vendors
                    if vendor.id != current_vendor.id
                    and len(vendor.normalized_name.split()) >= 2
                    and current_vendor.normalized_name.startswith(vendor.normalized_name + " ")
                ]
                if alias_ids:
                    for invoice in db.scalars(
                        select(Document).where(
                            Document.workspace_id == document.workspace_id,
                            Document.kind == "invoice",
                            Document.vendor_id.in_(alias_ids),
                            Document.id != document.id,
                        )
                    ):
                        refresh_findings(db, invoice)
        job.progress = 95
        db.commit()
        add_event(db, job, "validated", "Arithmetic and purchase order checks complete")
        return {}
    raise AssertionError("Workflow resource iterator must yield or raise")


def generate_findings(state: WorkflowState) -> dict:
    from sqlalchemy import func

    from .models import Finding

    for db, document, job in _rows(state):
        count = (
            db.scalar(
                select(func.count(Finding.id)).where(
                    Finding.document_id == document.id,
                    Finding.extraction_version == document.version,
                )
            )
            or 0
        )
        job.progress = 100
        db.commit()
        add_event(db, job, "review", f"Ready for review: {count} findings")
        return {"finding_count": count, "version": document.version}
    raise AssertionError("Workflow resource iterator must yield or raise")


def human_review(state: WorkflowState) -> dict:
    decision = interrupt(
        {
            "document_id": state["document_id"],
            "version": state["version"],
            "finding_count": state.get("finding_count", 0),
            "action": "Review current version before approval",
        }
    )
    return {
        "approved": bool(decision.get("approved")),
        "version": int(decision.get("version", state["version"])),
        "actor_id": str(decision.get("actor_id", "")),
    }


def route_review(state: WorkflowState) -> str:
    return "approve" if state.get("approved") else END


def approve(state: WorkflowState) -> dict:
    # The API has already authenticated the actor; the graph still checks live version and role.
    with SessionLocal() as db:
        document = db.scalar(
            select(Document).where(
                Document.id == state["document_id"], Document.workspace_id == state["workspace_id"]
            )
        )
        actor_id = state.get("actor_id")
        actor = db.get(User, actor_id) if actor_id else None
        if (
            not document
            or not actor
            or actor.workspace_id != document.workspace_id
            or actor.role not in {"admin", "operator"}
        ):
            raise HTTPException(403, "Approval actor is invalid")
        approve_document(db, document, state["version"], actor)
    return {"approved": True}


def build_graph(checkpointer):
    # LangGraph accepts TypedDict schemas at runtime; ty's generic bound misses total=False.
    builder = StateGraph(WorkflowState)  # ty: ignore[invalid-argument-type]
    builder.add_node("ingest", ingest)
    builder.add_node("classify", classify)
    builder.add_node("extract", extract)
    builder.add_node("normalize", normalize)
    builder.add_node("validate", validate)
    builder.add_node("generate_findings", generate_findings)
    builder.add_node("human_review", human_review)
    builder.add_node("approve", approve)
    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "classify")
    builder.add_edge("classify", "extract")
    builder.add_edge("extract", "normalize")
    builder.add_edge("normalize", "validate")
    builder.add_edge("validate", "generate_findings")
    builder.add_edge("generate_findings", "human_review")
    builder.add_conditional_edges("human_review", route_review, {"approve": "approve", END: END})
    builder.add_edge("approve", END)
    return builder.compile(checkpointer=checkpointer)


@contextmanager
def graph_context():
    settings = get_settings()
    if settings.database_url.startswith("postgresql"):
        pg_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        with PostgresSaver.from_conn_string(pg_url) as saver:
            saver.setup()
            yield build_graph(saver)
    else:
        settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(settings.checkpoint_path)) as saver:
            saver.setup()
            yield build_graph(saver)


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status == "cancelled":
            return
        workspace_id, document_id = job.workspace_id, job.document_id
    log.info(
        json.dumps(
            {
                "event": "job_started",
                "job_id": job_id,
                "document_id": document_id,
                "workspace_id": workspace_id,
            }
        )
    )
    config = {"configurable": {"thread_id": f"{workspace_id}:{document_id}"}, "recursion_limit": 30}
    heartbeat_stop = Event()

    def renew_lease() -> None:
        while not heartbeat_stop.wait(max(5, get_settings().job_lease_seconds // 4)):
            with SessionLocal() as heartbeat_db:
                heartbeat_db.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == "processing")
                    .values(
                        lease_until=utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
                    )
                )
                heartbeat_db.commit()

    heartbeat = Thread(target=renew_lease, name=f"lease-{job_id[:8]}", daemon=True)
    heartbeat.start()
    try:
        with graph_context() as graph:
            snapshot = graph.get_state(config)
            if snapshot.next and snapshot.values:
                if snapshot.next == ("human_review",):
                    pass
                else:
                    graph.invoke(None, config)
            else:
                graph.invoke(
                    {"workspace_id": workspace_id, "document_id": document_id, "job_id": job_id},
                    config,
                )
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job and job.status != "cancelled":
                job.status = "complete"
                job.progress = 100
                job.lease_until = None
                db.commit()
                add_event(db, job, "complete", "Processing complete; awaiting review")
                log.info(json.dumps({"event": "job_complete", "job_id": job_id}))
    except JobCancelled:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                add_event(db, job, "cancelled", "Processing cancelled")
                log.info(json.dumps({"event": "job_cancelled", "job_id": job_id}))
    except Exception as exc:
        log.error(
            json.dumps({"event": "job_failed", "job_id": job_id, "error_type": type(exc).__name__})
        )
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                if isinstance(exc, ConnectedPageError):
                    job.error = f"{type(exc).__name__}: {exc}"[:1000]
                elif get_settings().mode == "CONNECTED":
                    job.error = (
                        f"{type(exc).__name__}: model extraction failed; "
                        "verify provider configuration and retry"
                    )
                else:
                    job.error = f"{type(exc).__name__}: {exc}"[:1000]
                job.lease_until = None
                document = db.get(Document, job.document_id)
                if document:
                    document.status = "failed"
                db.commit()
                add_event(db, job, "failed", job.error or "Processing failed")
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=2)


def resume_approval(document: Document, version: int, user: User) -> None:
    config = {
        "configurable": {"thread_id": f"{document.workspace_id}:{document.id}"},
        "recursion_limit": 30,
    }
    with graph_context() as graph:
        snapshot = graph.get_state(config)
        if "human_review" not in snapshot.next or snapshot.values.get("version") != version:
            # A correction or newly available PO can invalidate an approval after
            # the original graph has ended. The server reopens its review node for
            # the live version; the approval node checks role, version and hash.
            with SessionLocal() as db:
                finding_count = (
                    db.scalar(
                        select(func.count(Finding.id)).where(
                            Finding.document_id == document.id,
                            Finding.extraction_version == version,
                            Finding.status == "open",
                        )
                    )
                    or 0
                )
            graph.update_state(
                config,
                {
                    "workspace_id": document.workspace_id,
                    "document_id": document.id,
                    "version": version,
                    "finding_count": finding_count,
                    "approved": False,
                    "actor_id": "",
                },
                as_node="generate_findings",
            )
            graph.invoke(None, config)
            snapshot = graph.get_state(config)
        if "human_review" not in snapshot.next:
            raise HTTPException(409, "Document is not awaiting graph review")
        graph.invoke(
            Command(resume={"approved": True, "version": version, "actor_id": user.id}), config
        )


class Worker:
    def __init__(self):
        self.stop_event = Event()
        self.thread: Thread | None = None

    def start(self) -> None:
        self.thread = Thread(target=self.loop, name="invoicelens-worker", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def loop(self) -> None:
        settings = get_settings()
        while not self.stop_event.is_set():
            job_id = self.claim()
            if job_id:
                run_job(job_id)
            else:
                self.stop_event.wait(settings.worker_poll_seconds)

    def claim(self) -> str | None:
        with SessionLocal() as db:
            now = utcnow()
            candidate = db.scalar(
                select(Job.id)
                .where(
                    or_(
                        Job.status == "queued",
                        (Job.status == "processing") & (Job.lease_until < now),
                    )
                )
                .order_by(Job.created_at)
                .limit(1)
            )
            if not candidate:
                return None
            changed = db.execute(
                update(Job)
                .where(
                    Job.id == candidate,
                    or_(
                        Job.status == "queued",
                        (Job.status == "processing") & (Job.lease_until < now),
                    ),
                )
                .values(
                    status="processing",
                    attempts=Job.attempts + 1,
                    lease_until=now + timedelta(seconds=get_settings().job_lease_seconds),
                    error=None,
                )
            )
            db.commit()
            return candidate if cast(Any, changed).rowcount == 1 else None
