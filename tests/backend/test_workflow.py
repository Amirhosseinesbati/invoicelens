import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from invoicelens.db import SessionLocal
from invoicelens.extraction import iter_pages
from invoicelens.models import (
    ActionLedger,
    Document,
    DocumentPage,
    ExportJob,
    Job,
    JobEvent,
)
from invoicelens.service import get_export
from invoicelens.workflow import run_job
from reportlab.pdfgen import canvas
from sqlalchemy import func, select


def two_page_invoice() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    for index, lines in enumerate(
        (
            (
                "INVOICE",
                "Vendor: Retry Tools",
                "Invoice #: INV-RETRY-001 Date: 06/16/2026",
                "PO #: PO-RETRY-001 Currency: USD Due Date: 07/16/2026",
                "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT",
                "SKU-RETRY Test fitting 2 ea 50.00 100.00",
                "Subtotal: 100.00",
                "Tax: 0.00",
                "Freight: 0.00",
                "Discount: 0.00",
                "Total: 100.00",
            ),
            ("Second page supplemental terms for the retry test.",),
        )
    ):
        y = 740
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 20
        if index == 0:
            pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def matching_po() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 740
    for line in (
        "PURCHASE ORDER",
        "Vendor: Retry Tools",
        "PO #: PO-RETRY-001",
        "Date: 06/16/2026",
        "Currency: USD",
        "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT",
        "SKU-RETRY Test fitting 2 ea 50.00 100.00",
        "Subtotal: 100.00",
        "Tax: 0.00",
        "Freight: 0.00",
        "Discount: 0.00",
        "Total: 100.00",
    ):
        pdf.drawString(50, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def test_retry_finishes_missing_pages_checkpoint_approval_and_concurrent_export(
    client, operator_headers
):
    content = two_page_invoice()
    uploaded = client.post(
        "/api/uploads",
        headers=operator_headers,
        files=[("files", ("partial.pdf", content, "application/pdf"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["items"][0]["document_id"]
    job_id = uploaded.json()["items"][0]["job_id"]
    first = next(iter_pages(content, "application/pdf"))
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        job = db.get(Job, job_id)
        db.add(
            DocumentPage(
                workspace_id=document.workspace_id,
                document_id=document_id,
                page_number=1,
                text=first.text,
                source_type=first.source_type,
                width=first.width,
                height=first.height,
                words=first.words,
            )
        )
        job.status = "failed"
        job.current_page = 1
        job.progress = 15
        document.status = "failed"
        db.commit()

    retried = client.post(f"/api/jobs/{job_id}/retry", headers=operator_headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "queued"
    run_job(job_id)

    response = client.get(f"/api/documents/{document_id}", headers=operator_headers)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert [page["page_number"] for page in detail["pages"]] == [1, 2]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "complete"
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(JobEvent.id)).where(
                    JobEvent.job_id == job_id, JobEvent.type == "page"
                )
            )
            == 1
        )

    approved = client.post(
        f"/api/documents/{document_id}/approve",
        headers=operator_headers,
        json={"version": detail["version"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval"]["version"] == 1

    start = Barrier(2)

    def export_once() -> bytes:
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            start.wait(timeout=5)
            return get_export(db, document, "json")[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_export, second_export = list(
            pool.map(lambda _index: export_once(), range(2))
        )
    assert first_export == second_export
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(ExportJob.id)).where(
                    ExportJob.document_id == document_id, ExportJob.format == "json"
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(ActionLedger.id)).where(
                    ActionLedger.document_id == document_id,
                    ActionLedger.kind == "export",
                )
            )
            == 1
        )
    po_upload = client.post(
        "/api/uploads",
        files=[("files", ("retry-po.pdf", matching_po(), "application/pdf"))],
    )
    assert po_upload.status_code == 200, po_upload.text
    run_job(po_upload.json()["items"][0]["job_id"])
    after_po = client.get(f"/api/documents/{document_id}").json()
    assert after_po["version"] == 1
    assert after_po["approval"] is None
    assert after_po["matches"][0]["status"] == "matched"
    reapproved = client.post(
        f"/api/documents/{document_id}/approve", json={"version": 1}
    )
    assert reapproved.status_code == 200, reapproved.text
