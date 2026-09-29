import asyncio
import io
import json
from contextlib import asynccontextmanager

import pypdfium2 as pdfium
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, create_schema, get_db
from .extraction import ocr_available
from .models import (
    Document,
    ExportJob,
    ExtractionVersion,
    Finding,
    Invoice,
    Job,
    JobEvent,
    User,
    Vendor,
)
from .schemas import (
    ApprovalRequest,
    CorrectionRequest,
    DecisionRequest,
    DocumentDetail,
    DocumentSummary,
    ExtractionVersionView,
    JobView,
    LineMatchDecisionRequest,
    LoginRequest,
    LoginResponse,
    MatchDecisionRequest,
    OverviewView,
    SettingsView,
    UploadResponse,
    UserView,
    VendorView,
)
from .security import (
    TOKEN_MAX_AGE,
    create_token,
    current_user,
    operator,
    password_hash,
    seed_demo_users,
)
from .service import (
    apply_correction,
    approval_blocker_count,
    approval_ready,
    approve_document,
    decide_finding,
    decide_line_match,
    decide_match,
    detail,
    get_document,
    get_export,
    get_job,
    job_record,
    refresh_findings,
    summary,
    upload_document,
)
from .storage import UploadError, storage_path
from .workflow import Worker, resume_approval

worker = Worker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if get_settings().mode == "DEMO":
        create_schema()
        with SessionLocal() as db:
            seed_demo_users(db)
    if get_settings().auto_worker:
        worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(title="InvoiceLens API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def user_record(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "workspace_id": user.workspace_id,
        "workspace_name": user.workspace.name,
    }


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count(User.id)))
    return {"status": "ok", "mode": get_settings().mode}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().casefold()))
    try:
        valid_password = bool(user and password_hash.verify(user.password_hash, payload.password))
    except VerifyMismatchError:
        valid_password = False
    if not valid_password or user is None:
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user)
    response.set_cookie(
        "invoicelens_session",
        token,
        max_age=TOKEN_MAX_AGE,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/api",
    )
    return {"user": user_record(user)}


@app.get("/api/auth/me", response_model=UserView)
def me(user: User = Depends(current_user)):
    return user_record(user)


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("invoicelens_session", path="/api")
    return {"ok": True}


@app.get("/api/overview", response_model=OverviewView)
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    documents = db.scalars(select(Document).where(Document.workspace_id == user.workspace_id)).all()
    open_findings = (
        db.scalar(
            select(func.count(Finding.id))
            .join(Document, Document.id == Finding.document_id)
            .where(
                Document.workspace_id == user.workspace_id,
                Finding.status == "open",
                Finding.extraction_version == Document.version,
            )
        )
        or 0
    )
    vendor_count = (
        db.scalar(select(func.count(Vendor.id)).where(Vendor.workspace_id == user.workspace_id))
        or 0
    )
    export_count = (
        db.scalar(
            select(func.count(ExportJob.id)).where(ExportJob.workspace_id == user.workspace_id)
        )
        or 0
    )
    return {
        "total_documents": len(documents),
        "needs_review": sum(d.status == "needs_review" for d in documents),
        "approved": sum(d.status == "approved" for d in documents),
        "processing": sum(d.status in {"queued", "processing"} for d in documents),
        "findings_open": open_findings,
        "vendors": vendor_count,
        "export_count": export_count,
    }


@app.get("/api/documents", response_model=list[DocumentSummary])
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)):
    documents = db.scalars(
        select(Document)
        .where(Document.workspace_id == user.workspace_id)
        .order_by(Document.created_at.desc())
    ).all()
    return [summary(db, document) for document in documents]


@app.get("/api/documents/{document_id}", response_model=DocumentDetail)
def document_detail(
    document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return detail(db, get_document(db, user.workspace_id, document_id))


def _version_record(version: ExtractionVersion) -> dict:
    return {
        "version": version.version,
        "source": version.source,
        "reason": version.reason,
        "created_at": version.created_at,
        "fields": version.data.get("fields", {}),
        "lines": [
            {"id": str(index), **line} for index, line in enumerate(version.data.get("lines", []))
        ],
        "content_hash": version.content_hash,
    }


@app.get("/api/documents/{document_id}/versions", response_model=list[ExtractionVersionView])
def document_versions(
    document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_document(db, user.workspace_id, document_id)
    versions = db.scalars(
        select(ExtractionVersion)
        .where(
            ExtractionVersion.workspace_id == user.workspace_id,
            ExtractionVersion.document_id == document_id,
        )
        .order_by(ExtractionVersion.version)
    ).all()
    return [_version_record(version) for version in versions]


@app.get("/api/documents/{document_id}/versions/{version}", response_model=ExtractionVersionView)
def document_version(
    document_id: str,
    version: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    get_document(db, user.workspace_id, document_id)
    row = db.scalar(
        select(ExtractionVersion).where(
            ExtractionVersion.workspace_id == user.workspace_id,
            ExtractionVersion.document_id == document_id,
            ExtractionVersion.version == version,
        )
    )
    if row is None:
        raise HTTPException(404, "Extraction version not found")
    return _version_record(row)


@app.get("/api/documents/{document_id}/source")
def source(document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    document = get_document(db, user.workspace_id, document_id)
    path = storage_path(user.workspace_id, document.storage_key)
    if not path.exists():
        raise HTTPException(404, "Source file missing")
    return FileResponse(
        path,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{document.id}{path.suffix}",
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/documents/{document_id}/pages/{page_number}/image")
def page_image(
    document_id: str,
    page_number: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    if page_number < 1 or page_number > len(document.pages):
        raise HTTPException(404, "Page not found")
    content = storage_path(user.workspace_id, document.storage_key).read_bytes()
    if document.content_type == "application/pdf":
        pdf = pdfium.PdfDocument(content)
        bitmap = pdf[page_number - 1].render(scale=1.5)
        output = io.BytesIO()
        bitmap.to_pil().save(output, format="PNG")
        png = output.getvalue()
        pdf.close()
    else:
        image = Image.open(io.BytesIO(content)).convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PNG")
        png = output.getvalue()
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/uploads", response_model=UploadResponse)
async def upload(
    files: list[UploadFile] = File(...),
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    if len(files) > 50:
        raise HTTPException(413, "Batch limit is 50 files")
    results = []
    for file in files:
        content = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
        try:
            document, job, deduplicated = upload_document(
                db, user.workspace_id, file.filename or "document", content
            )
            results.append(
                {
                    "document_id": document.id,
                    "job_id": job.id,
                    "status": job.status,
                    "deduplicated": deduplicated,
                    "error": None,
                }
            )
        except UploadError as exc:
            results.append(
                {
                    "document_id": None,
                    "job_id": None,
                    "status": "rejected",
                    "deduplicated": False,
                    "error": str(exc),
                    "filename": file.filename,
                }
            )
    return {"items": results}


@app.get("/api/jobs", response_model=list[JobView])
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    jobs = db.scalars(
        select(Job).where(Job.workspace_id == user.workspace_id).order_by(Job.created_at.desc())
    ).all()
    return [job_record(job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobView)
def job_detail(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return job_record(get_job(db, user.workspace_id, job_id))


@app.get("/api/jobs/{job_id}/events")
async def job_events(
    job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    get_job(db, user.workspace_id, job_id)
    workspace_id = user.workspace_id

    async def stream():
        after = 0
        while True:
            with SessionLocal() as event_db:
                rows = event_db.scalars(
                    select(JobEvent)
                    .where(
                        JobEvent.job_id == job_id,
                        JobEvent.workspace_id == workspace_id,
                        JobEvent.id > after,
                    )
                    .order_by(JobEvent.id)
                ).all()
                status = event_db.scalar(
                    select(Job.status).where(Job.id == job_id, Job.workspace_id == workspace_id)
                )
                for row in rows:
                    after = row.id
                    payload = {
                        "type": row.type,
                        "message": row.message,
                        "progress": row.progress,
                        "created_at": row.created_at.isoformat(),
                    }
                    yield f"id: {row.id}\ndata: {json.dumps(payload)}\n\n"
            if status in {"complete", "cancelled", "failed"}:
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.post("/api/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, user: User = Depends(operator), db: Session = Depends(get_db)):
    job = get_job(db, user.workspace_id, job_id)
    if job.status not in {"queued", "processing"}:
        raise HTTPException(409, "Only queued or processing jobs can be cancelled")
    job.status = "cancelled"
    job.lease_until = None
    document = get_document(db, user.workspace_id, job.document_id)
    document.status = "cancelled"
    db.commit()
    return job_record(job)


@app.post("/api/jobs/{job_id}/retry", response_model=JobView)
def retry_job(job_id: str, user: User = Depends(operator), db: Session = Depends(get_db)):
    job = get_job(db, user.workspace_id, job_id)
    if job.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled jobs can be retried")
    job.status = "queued"
    job.error = None
    job.lease_until = None
    document = get_document(db, user.workspace_id, job.document_id)
    document.status = "queued"
    db.commit()
    return job_record(job)


@app.post("/api/documents/{document_id}/corrections", response_model=DocumentDetail)
def correction(
    document_id: str,
    payload: CorrectionRequest,
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    apply_correction(db, document, user, payload.field, payload.value, payload.reason)
    db.refresh(document)
    return detail(db, document)


@app.post("/api/documents/{document_id}/revalidate", response_model=DocumentDetail)
def revalidate(document_id: str, user: User = Depends(operator), db: Session = Depends(get_db)):
    document = get_document(db, user.workspace_id, document_id)
    if document.version == 0:
        raise HTTPException(409, "Document has not been extracted")
    refresh_findings(db, document)
    db.refresh(document)
    return detail(db, document)


@app.post("/api/documents/{document_id}/matches/decision", response_model=DocumentDetail)
def match_decision(
    document_id: str,
    payload: MatchDecisionRequest,
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    decide_match(db, document, user, payload.version, payload.decision, payload.po_id, payload.note)
    db.refresh(document)
    return detail(db, document)


@app.post("/api/documents/{document_id}/line-matches/decision", response_model=DocumentDetail)
def line_match_decision(
    document_id: str,
    payload: LineMatchDecisionRequest,
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    decide_line_match(
        db,
        document,
        user,
        payload.version,
        payload.invoice_line_index,
        payload.po_line_id,
        payload.note,
    )
    db.refresh(document)
    return detail(db, document)


@app.post(
    "/api/documents/{document_id}/findings/{finding_id}/decisions", response_model=DocumentDetail
)
def finding_decision(
    document_id: str,
    finding_id: str,
    payload: DecisionRequest,
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    decide_finding(db, document, finding_id, user, payload.decision, payload.note)
    return detail(db, document)


@app.post("/api/documents/{document_id}/approve", response_model=DocumentDetail)
def approve(
    document_id: str,
    payload: ApprovalRequest,
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    if document.version != payload.version:
        raise HTTPException(409, "Document version changed; review latest extraction")
    if document.kind == "unknown":
        raise HTTPException(
            409, "Classify document as an invoice, credit note, or purchase order before approval"
        )
    if not approval_ready(db, document):
        raise HTTPException(409, "Document validation has not completed for this version")
    if document.approved_version == payload.version:
        approve_document(db, document, payload.version, user)
        db.refresh(document)
        return detail(db, document)
    if approval_blocker_count(db, document):
        raise HTTPException(409, "Resolve required matches and open errors before approval")
    resume_approval(document, payload.version, user)
    db.expire_all()
    document = get_document(db, user.workspace_id, document_id)
    return detail(db, document)


@app.get("/api/documents/{document_id}/exports")
def export(
    document_id: str,
    format: str = Query(...),
    user: User = Depends(operator),
    db: Session = Depends(get_db),
):
    document = get_document(db, user.workspace_id, document_id)
    content, filename = get_export(db, document, format)
    mime = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
    }[format]
    return Response(
        content,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/vendors", response_model=list[VendorView])
def vendors(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Vendor).where(Vendor.workspace_id == user.workspace_id).order_by(Vendor.name)
    ).all()
    return [
        {
            "id": vendor.id,
            "name": vendor.name,
            "invoice_count": db.scalar(
                select(func.count(Invoice.id)).where(
                    Invoice.vendor_id == vendor.id, Invoice.workspace_id == user.workspace_id
                )
            )
            or 0,
        }
        for vendor in rows
    ]


@app.get("/api/settings", response_model=SettingsView)
def settings(user: User = Depends(current_user)):
    configured = bool(get_settings().openai_api_key and get_settings().openai_model)
    return {
        "mode": get_settings().mode,
        "model_configured": configured,
        "ocr_available": ocr_available(),
        "workspace_name": user.workspace.name,
        "export_formats": ["csv", "xlsx", "json"],
    }
