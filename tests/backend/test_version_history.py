import io

from invoicelens.db import SessionLocal
from invoicelens.models import Document
from invoicelens.workflow import run_job
from reportlab.pdfgen import canvas


def _invoice_pdf(number: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    for position, line in enumerate(
        [
            "INVOICE",
            "Vendor: Version History Supplies",
            f"Invoice #: {number} Date: 06/16/2026",
            "PO #: PO-VERSIONS-001 Currency: USD Due Date: 07/16/2026",
            "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT",
            "VH-1 Safety clamp 2 ea 10.00 20.00",
            "Subtotal: 20.00",
            "Tax: 0.00",
            "Freight: 0.00",
            "Discount: 0.00",
            "Total: 20.00",
        ]
    ):
        pdf.drawString(50, 740 - position * 20, line)
    pdf.save()
    return buffer.getvalue()


def _upload_processed_invoice(client, number: str) -> str:
    response = client.post(
        "/api/uploads",
        files=[
            ("files", ("version-history.pdf", _invoice_pdf(number), "application/pdf"))
        ],
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["status"] == "queued"
    run_job(item["job_id"])
    return item["document_id"]


def test_extraction_versions_are_readable_and_workspace_scoped(
    client, operator_headers
):
    document_id = _upload_processed_invoice(client, "INV-VERSIONS-001")
    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    initial = detail.json()

    corrected = client.post(
        f"/api/documents/{document_id}/corrections",
        json={
            "field": "number",
            "value": "INV-VERSIONS-EDITED",
            "reason": "Invoice number reviewed",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["version"] == 2

    path = f"/api/documents/{document_id}/versions"
    response = client.get(path)
    assert response.status_code == 200, response.text
    versions = response.json()
    assert [version["version"] for version in versions] == [1, 2]
    assert all(
        set(version)
        == {
            "version",
            "source",
            "reason",
            "created_at",
            "fields",
            "lines",
            "content_hash",
        }
        for version in versions
    )
    assert versions[0]["reason"] is None
    assert versions[0]["fields"] == initial["fields"]
    assert versions[0]["lines"] == initial["lines"]
    assert versions[0]["fields"]["number"]["value"] == "INV-VERSIONS-001"
    assert versions[1]["source"] == "correction"
    assert versions[1]["reason"] == "Invoice number reviewed"
    assert versions[1]["fields"]["number"]["value"] == "INV-VERSIONS-EDITED"
    assert versions[1]["fields"] == corrected.json()["fields"]
    assert versions[0]["content_hash"] != versions[1]["content_hash"]
    assert all(len(version["content_hash"]) == 64 for version in versions)

    first = client.get(f"{path}/1")
    assert first.status_code == 200
    assert first.json() == versions[0]
    assert client.get(f"{path}/99").status_code == 404

    viewer = client.post(
        "/api/auth/login",
        json={"email": "viewer@example.com", "password": "DemoPass123!"},
    )
    assert viewer.status_code == 200
    assert client.get(path).json() == versions
    assert client.get(f"{path}/1").json() == versions[0]

    other = client.post(
        "/api/auth/login",
        json={"email": "operator2@example.com", "password": "DemoPass123!"},
    )
    assert other.status_code == 200
    assert client.get(path).status_code == 404
    assert client.get(f"{path}/1").status_code == 404


def test_unknown_document_cannot_be_approved(client, operator_headers):
    document_id = _upload_processed_invoice(client, "INV-UNKNOWN-001")
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        document.kind = "unknown"
        version = document.version
        db.commit()

    response = client.post(
        f"/api/documents/{document_id}/approve", json={"version": version}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Classify document as an invoice, credit note, or purchase order before approval"
    )
