import io
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from fastapi import HTTPException
from invoicelens.db import SessionLocal
from invoicelens.models import Document, User
from invoicelens.service import approve_document
from invoicelens.workflow import run_job
from reportlab.pdfgen import canvas
from sqlalchemy import select


def source_pdf(
    kind: str,
    vendor: str,
    number: str,
    po_number: str,
    rows: list[tuple[str, int, str]],
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(612, 792))
    total = sum((Decimal(qty) * Decimal(price) for _, qty, price in rows), Decimal(0))
    heading = "PURCHASE ORDER" if kind == "po" else "INVOICE"
    lines = [heading, f"Vendor: {vendor}"]
    if kind == "invoice":
        lines.append(f"Invoice #: {number}")
    lines.extend(
        [
            f"PO #: {po_number}",
            "Date: 06/16/2026",
            "Currency: USD",
            "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT",
        ]
    )
    for sku, qty, price in rows:
        lines.append(
            f"{sku} Test fitting {qty} ea {price} {Decimal(qty) * Decimal(price):.2f}"
        )
    lines.extend(
        [
            f"Subtotal: {total:.2f}",
            "Tax: 0.00",
            "Freight: 0.00",
            "Discount: 0.00",
            f"Total: {total:.2f}",
        ]
    )
    y = 740
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def upload_and_process(client, filename: str, content: bytes) -> dict:
    response = client.post(
        "/api/uploads", files=[("files", (filename, content, "application/pdf"))]
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["status"] == "queued", item
    run_job(item["job_id"])
    detail = client.get(f"/api/documents/{item['document_id']}")
    assert detail.status_code == 200, detail.text
    return detail.json()


def test_ambiguous_po_requires_versioned_choice_and_reject_all(
    client, operator_headers
):
    po_a = upload_and_process(
        client,
        "select-po-a.pdf",
        source_pdf("po", "Select Tools", "", "PO-SELECT-1", [("SKU-SEL", 1, "20.00")]),
    )
    po_b = upload_and_process(
        client,
        "select-po-b.pdf",
        source_pdf("po", "Select Tools", "", "PO-SELECT-1", [("SKU-SEL", 1, "25.00")]),
    )
    invoice = upload_and_process(
        client,
        "select-invoice.pdf",
        source_pdf(
            "invoice",
            "Select Tools",
            "INV-SELECT-1",
            "PO-SELECT-1",
            [("SKU-SEL", 1, "20.00")],
        ),
    )
    invoice_id = invoice["id"]
    assert {match["document_id"] for match in invoice["matches"]} == {
        po_a["id"],
        po_b["id"],
    }
    assert any(f["code"] == "AMBIGUOUS_PO" for f in invoice["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve", json={"version": invoice["version"]}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/documents/{invoice_id}/matches/decision",
            json={
                "version": 1,
                "decision": "selected",
                "po_id": "not-a-current-proposal",
            },
        ).status_code
        == 422
    )
    chosen_po = next(
        match for match in invoice["matches"] if match["document_id"] == po_a["id"]
    )
    selected = client.post(
        f"/api/documents/{invoice_id}/matches/decision",
        json={
            "version": invoice["version"],
            "decision": "selected",
            "po_id": chosen_po["po_id"],
        },
    )
    assert selected.status_code == 200, selected.text
    version_two = selected.json()
    assert version_two["version"] == 2
    assert version_two["match_resolution"]["po_id"] == chosen_po["po_id"]
    assert {match["status"] for match in version_two["matches"]} == {
        "selected",
        "rejected",
    }
    assert not any(f["code"] == "AMBIGUOUS_PO" for f in version_two["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve",
            json={"version": version_two["version"]},
        ).status_code
        == 200
    )
    first_export = client.get(f"/api/documents/{invoice_id}/exports?format=json")
    assert first_export.status_code == 200
    assert first_export.json()["document_version"] == 2
    rejected = client.post(
        f"/api/documents/{invoice_id}/matches/decision",
        json={
            "version": 2,
            "decision": "rejected",
            "po_id": None,
            "note": "No PO accepted",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["version"] == 3
    assert rejected.json()["approval"] is None
    assert (
        client.get(f"/api/documents/{invoice_id}/exports?format=json").status_code
        == 409
    )
    assert rejected.json()["match_resolution"]["decision"] == "rejected"
    assert all(match["status"] == "rejected" for match in rejected.json()["matches"])
    repeated = client.post(
        f"/api/documents/{invoice_id}/matches/decision",
        json={"version": 3, "decision": "rejected", "po_id": None},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["version"] == 3
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve", json={"version": 3}
        ).status_code
        == 200
    )
    second_export = client.get(f"/api/documents/{invoice_id}/exports?format=json")
    assert second_export.status_code == 200
    assert second_export.json()["document_version"] == 3


def test_ambiguous_po_line_requires_explicit_line_mapping(client, operator_headers):
    upload_and_process(
        client,
        "line-po.pdf",
        source_pdf(
            "po",
            "Line Tools",
            "",
            "PO-LINE-1",
            [("SKU-LINE", 1, "20.00"), ("SKU-LINE", 1, "25.00")],
        ),
    )
    invoice = upload_and_process(
        client,
        "line-invoice.pdf",
        source_pdf(
            "invoice",
            "Line Tools",
            "INV-LINE-1",
            "PO-LINE-1",
            [("SKU-LINE", 1, "20.00")],
        ),
    )
    invoice_id = invoice["id"]
    finding = next(
        f for f in invoice["findings"] if f["code"] == "AMBIGUOUS_LINE_MATCH"
    )
    assert finding["details"]["invoice_line_indices"] == [0]
    assert len(finding["details"]["candidates"]) == 2
    assert invoice["line_match_candidates"][0]["invoice_line_index"] == 0
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve", json={"version": 1}
        ).status_code
        == 409
    )
    accepted_finding = client.post(
        f"/api/documents/{invoice_id}/findings/{finding['id']}/decisions",
        json={"decision": "accepted"},
    )
    assert accepted_finding.status_code == 200
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve", json={"version": 1}
        ).status_code
        == 409
    )
    matching_line = next(
        candidate
        for candidate in finding["details"]["candidates"]
        if candidate["unit_price"] == "20.00"
    )
    mapped = client.post(
        f"/api/documents/{invoice_id}/line-matches/decision",
        json={
            "version": 1,
            "invoice_line_index": 0,
            "po_line_id": matching_line["po_line_id"],
        },
    )
    assert mapped.status_code == 200, mapped.text
    assert mapped.json()["version"] == 2
    assert mapped.json()["line_matches"] == {"0": matching_line["po_line_id"]}
    assert mapped.json()["line_match_candidates"][0]["invoice_line_index"] == 0
    assert not any(
        f["code"] == "AMBIGUOUS_LINE_MATCH" for f in mapped.json()["findings"]
    )
    assert (
        client.post(
            f"/api/documents/{invoice_id}/approve", json={"version": 2}
        ).status_code
        == 200
    )


def test_repeated_invoice_sku_auto_maps_to_one_po_line(client, operator_headers):
    upload_and_process(
        client,
        "partial-po.pdf",
        source_pdf(
            "po", "Partial Tools", "", "PO-PARTIAL-1", [("SKU-PART", 5, "20.00")]
        ),
    )
    invoice = upload_and_process(
        client,
        "partial-invoice.pdf",
        source_pdf(
            "invoice",
            "Partial Tools",
            "INV-PARTIAL-1",
            "PO-PARTIAL-1",
            [("SKU-PART", 2, "20.00"), ("SKU-PART", 3, "20.00")],
        ),
    )
    assert len(invoice["lines"]) == 2
    assert set(invoice["line_matches"]) == {"0", "1"}
    assert invoice["line_matches"]["0"] == invoice["line_matches"]["1"]
    assert not any(f["code"] == "AMBIGUOUS_LINE_MATCH" for f in invoice["findings"])
    assert not any(f["code"] == "QUANTITY_OVER_PO_LINE" for f in invoice["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice['id']}/approve",
            json={"version": invoice["version"]},
        ).status_code
        == 200
    )


def test_po_price_comparison_requires_verified_source_rows(client, operator_headers):
    po = upload_and_process(
        client,
        "verified-price-po.pdf",
        source_pdf(
            "po",
            "Verified Price Tools",
            "",
            "PO-VERIFY-PRICE",
            [("SKU-VP", 2, "20.00")],
        ),
    )
    invoice = upload_and_process(
        client,
        "verified-price-invoice.pdf",
        source_pdf(
            "invoice",
            "Verified Price Tools",
            "INV-VERIFY-PRICE",
            "PO-VERIFY-PRICE",
            [("SKU-VP", 2, "20.00")],
        ),
    )
    assert not any(f["code"] == "UNIT_PRICE_MISMATCH" for f in invoice["findings"])

    damaged = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.unit_price",
            "value": "30.00",
            "reason": "Unverified PO price reading",
        },
    )
    assert damaged.status_code == 200, damaged.text
    refreshed = client.get(f"/api/documents/{invoice['id']}").json()
    assert any(f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"])
    assert not any(f["code"] == "UNIT_PRICE_MISMATCH" for f in refreshed["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice['id']}/approve",
            json={"version": invoice["version"]},
        ).status_code
        == 409
    )

    repaired = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.amount",
            "value": "60.00",
            "reason": "Confirmed PO amount",
        },
    )
    assert repaired.status_code == 200, repaired.text
    refreshed = client.get(f"/api/documents/{invoice['id']}").json()
    assert not any(
        f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"]
    )
    assert any(f["code"] == "UNIT_PRICE_MISMATCH" for f in refreshed["findings"])


def test_po_quantity_comparison_requires_verified_source_rows(client, operator_headers):
    po = upload_and_process(
        client,
        "verified-quantity-po.pdf",
        source_pdf(
            "po",
            "Verified Quantity Tools",
            "",
            "PO-VERIFY-QTY",
            [("SKU-VQ", 2, "20.00")],
        ),
    )
    invoice = upload_and_process(
        client,
        "verified-quantity-invoice.pdf",
        source_pdf(
            "invoice",
            "Verified Quantity Tools",
            "INV-VERIFY-QTY",
            "PO-VERIFY-QTY",
            [("SKU-VQ", 3, "20.00")],
        ),
    )
    assert any(f["code"] == "QUANTITY_OVER_PO" for f in invoice["findings"])

    damaged = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.quantity",
            "value": None,
            "reason": "Unreadable PO quantity",
        },
    )
    assert damaged.status_code == 200, damaged.text
    refreshed = client.get(f"/api/documents/{invoice['id']}").json()
    assert any(f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"])
    assert not any(f["code"] == "QUANTITY_OVER_PO" for f in refreshed["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice['id']}/approve",
            json={"version": invoice["version"]},
        ).status_code
        == 409
    )

    repaired = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.quantity",
            "value": "2",
            "reason": "Confirmed PO quantity",
        },
    )
    assert repaired.status_code == 200, repaired.text
    refreshed = client.get(f"/api/documents/{invoice['id']}").json()
    assert not any(
        f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"]
    )
    assert any(f["code"] == "QUANTITY_OVER_PO" for f in refreshed["findings"])


def test_same_price_po_rows_require_mapping_and_check_mapped_quantity(
    client, operator_headers
):
    upload_and_process(
        client,
        "same-price-po.pdf",
        source_pdf(
            "po",
            "Mapped Tools",
            "",
            "PO-MAPPED-1",
            [("SKU-MAP", 3, "20.00"), ("SKU-MAP", 8, "20.00")],
        ),
    )
    invoice = upload_and_process(
        client,
        "same-price-invoice.pdf",
        source_pdf(
            "invoice",
            "Mapped Tools",
            "INV-MAPPED-1",
            "PO-MAPPED-1",
            [("SKU-MAP", 2, "20.00"), ("SKU-MAP", 2, "20.00")],
        ),
    )
    document_id = invoice["id"]
    finding = next(
        f for f in invoice["findings"] if f["code"] == "AMBIGUOUS_LINE_MATCH"
    )
    assert finding["details"]["invoice_line_indices"] == [0, 1]
    assert len(invoice["line_match_candidates"]) == 2
    assert len(invoice["line_match_candidates"][0]["candidates"]) == 2
    small, large = sorted(
        finding["details"]["candidates"], key=lambda c: int(c["quantity"])
    )
    for index in (0, 1):
        response = client.post(
            f"/api/documents/{document_id}/line-matches/decision",
            json={
                "version": invoice["version"],
                "invoice_line_index": index,
                "po_line_id": small["po_line_id"],
            },
        )
        assert response.status_code == 200, response.text
        invoice = response.json()
    assert invoice["line_matches"] == {
        "0": small["po_line_id"],
        "1": small["po_line_id"],
    }
    assert not any(f["code"] == "AMBIGUOUS_LINE_MATCH" for f in invoice["findings"])
    assert any(f["code"] == "QUANTITY_OVER_PO_LINE" for f in invoice["findings"])
    assert (
        client.post(
            f"/api/documents/{document_id}/approve",
            json={"version": invoice["version"]},
        ).status_code
        == 409
    )
    response = client.post(
        f"/api/documents/{document_id}/line-matches/decision",
        json={
            "version": invoice["version"],
            "invoice_line_index": 1,
            "po_line_id": large["po_line_id"],
        },
    )
    assert response.status_code == 200, response.text
    invoice = response.json()
    assert not any(f["code"] == "QUANTITY_OVER_PO_LINE" for f in invoice["findings"])
    assert (
        client.post(
            f"/api/documents/{document_id}/approve",
            json={"version": invoice["version"]},
        ).status_code
        == 200
    )


def test_approved_invoices_share_po_quantity_and_po_correction_revokes_approval(
    client, operator_headers
):
    po = upload_and_process(
        client,
        "claim-po.pdf",
        source_pdf("po", "Claim Tools", "", "PO-CLAIM-1", [("SKU-CLAIM", 10, "10.00")]),
    )
    first = upload_and_process(
        client,
        "claim-first.pdf",
        source_pdf(
            "invoice",
            "Claim Tools",
            "INV-CLAIM-1",
            "PO-CLAIM-1",
            [("SKU-CLAIM", 6, "10.00")],
        ),
    )
    second = upload_and_process(
        client,
        "claim-second.pdf",
        source_pdf(
            "invoice",
            "Claim Tools",
            "INV-CLAIM-2",
            "PO-CLAIM-1",
            [("SKU-CLAIM", 6, "10.00")],
        ),
    )
    assert not any(f["code"] == "QUANTITY_OVER_PO" for f in second["findings"])
    assert (
        client.post(
            f"/api/documents/{first['id']}/approve", json={"version": first["version"]}
        ).status_code
        == 200
    )
    over_claim = client.post(
        f"/api/documents/{second['id']}/approve", json={"version": second["version"]}
    )
    assert over_claim.status_code == 409
    assert "across approved invoices" in over_claim.json()["detail"]
    assert (
        client.get(f"/api/documents/{first['id']}/exports?format=json").status_code
        == 200
    )

    corrected = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.quantity",
            "value": "5",
            "reason": "Revised PO quantity",
        },
    )
    assert corrected.status_code == 200, corrected.text
    refreshed = client.get(f"/api/documents/{first['id']}").json()
    assert refreshed["approval"] is None
    assert any(f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"])
    assert not any(f["code"] == "QUANTITY_OVER_PO" for f in refreshed["findings"])
    assert any(
        h["action"] == "po_correction_invalidation" for h in refreshed["history"]
    )
    assert (
        client.get(f"/api/documents/{first['id']}/exports?format=json").status_code
        == 409
    )

    repeated = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.quantity",
            "value": "5",
            "reason": "Revised PO quantity",
        },
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["version"] == corrected.json()["version"]
    assert len(repeated.json()["history"]) == len(corrected.json()["history"])

    repaired = client.post(
        f"/api/documents/{po['id']}/corrections",
        json={
            "field": "lines.0.amount",
            "value": "50.00",
            "reason": "Confirmed revised PO line amount",
        },
    )
    assert repaired.status_code == 200, repaired.text
    refreshed = client.get(f"/api/documents/{first['id']}").json()
    assert not any(
        f["code"] == "PO_LINE_SOURCE_UNVERIFIED" for f in refreshed["findings"]
    )
    assert any(f["code"] == "QUANTITY_OVER_PO" for f in refreshed["findings"])


def test_concurrent_approvals_cannot_both_claim_same_po_capacity(
    client, operator_headers
):
    upload_and_process(
        client,
        "race-po.pdf",
        source_pdf("po", "Race Tools", "", "PO-RACE-1", [("SKU-RACE", 10, "10.00")]),
    )
    invoices = [
        upload_and_process(
            client,
            f"race-{index}.pdf",
            source_pdf(
                "invoice",
                "Race Tools",
                f"INV-RACE-{index}",
                "PO-RACE-1",
                [("SKU-RACE", 6, "10.00")],
            ),
        )
        for index in (1, 2)
    ]
    start = Barrier(2)

    def approve_once(document_id: str) -> int:
        with SessionLocal() as db:
            document = db.get(Document, document_id)
            user = db.scalar(select(User).where(User.email == "operator@example.com"))
            assert document is not None and user is not None
            start.wait(timeout=5)
            try:
                approve_document(db, document, document.version, user)
            except HTTPException as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(approve_once, [item["id"] for item in invoices]))
    assert outcomes == [200, 409]


def test_late_vendor_name_adds_ambiguity_until_corrected(client, operator_headers):
    upload_and_process(
        client,
        "vendor-one.pdf",
        source_pdf("invoice", "North Quay Fasteners", "INV-VENDOR-A", "PO-VA", []),
    )
    alias = upload_and_process(
        client,
        "vendor-alias.pdf",
        source_pdf("invoice", "North Quay", "INV-VENDOR-ALIAS", "PO-VX", []),
    )
    alias_id = alias["id"]
    assert not any(f["code"] == "AMBIGUOUS_VENDOR" for f in alias["findings"])
    assert (
        client.post(
            f"/api/documents/{alias_id}/approve", json={"version": 1}
        ).status_code
        == 200
    )
    upload_and_process(
        client,
        "vendor-two.pdf",
        source_pdf("invoice", "North Quay Fabrication", "INV-VENDOR-B", "PO-VB", []),
    )
    refreshed = client.get(f"/api/documents/{alias_id}").json()
    assert refreshed["version"] == 1
    assert refreshed["approval"] is None
    ambiguous = next(
        f for f in refreshed["findings"] if f["code"] == "AMBIGUOUS_VENDOR"
    )
    assert len(ambiguous["details"]["candidate_vendors"]) == 2
    assert (
        client.post(
            f"/api/documents/{alias_id}/approve", json={"version": 1}
        ).status_code
        == 409
    )
    corrected = client.post(
        f"/api/documents/{alias_id}/corrections",
        json={
            "field": "vendor",
            "value": "North Quay Fasteners",
            "reason": "Resolved alias",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["version"] == 2
    assert not any(
        f["code"] == "AMBIGUOUS_VENDOR" for f in corrected.json()["findings"]
    )
    assert (
        client.post(
            f"/api/documents/{alias_id}/approve", json={"version": 2}
        ).status_code
        == 200
    )


def test_exact_po_prefers_same_vendor_across_duplicate_identifiers(
    client, operator_headers
):
    own_po = upload_and_process(
        client,
        "shared-po-own.pdf",
        source_pdf(
            "po", "Harbor Bolts", "", "PO-SHARED-1", [("SKU-SHARED", 1, "30.00")]
        ),
    )
    foreign_po = upload_and_process(
        client,
        "shared-po-other.pdf",
        source_pdf(
            "po", "River Bolts", "", "PO-SHARED-1", [("SKU-SHARED", 1, "40.00")]
        ),
    )
    invoice = upload_and_process(
        client,
        "shared-po-invoice.pdf",
        source_pdf(
            "invoice",
            "Harbor Bolts",
            "INV-SHARED-1",
            "PO-SHARED-1",
            [("SKU-SHARED", 1, "30.00")],
        ),
    )
    assert {match["document_id"] for match in invoice["matches"]} == {
        own_po["id"],
        foreign_po["id"],
    }
    assert (
        next(match for match in invoice["matches"] if match["status"] == "matched")[
            "document_id"
        ]
        == own_po["id"]
    )
    assert not any(f["code"] == "AMBIGUOUS_PO" for f in invoice["findings"])
    assert (
        client.post(
            f"/api/documents/{invoice['id']}/approve", json={"version": 1}
        ).status_code
        == 200
    )


def test_missing_structured_po_id_is_not_fuzzy_neighbor(client, operator_headers):
    upload_and_process(
        client,
        "neighbor-one.pdf",
        source_pdf(
            "po", "Neighbor Tools", "", "PO-NEIGHBOR-001", [("SKU-N", 1, "10.00")]
        ),
    )
    upload_and_process(
        client,
        "neighbor-three.pdf",
        source_pdf(
            "po", "Neighbor Tools", "", "PO-NEIGHBOR-003", [("SKU-N", 1, "10.00")]
        ),
    )
    invoice = upload_and_process(
        client,
        "neighbor-two-invoice.pdf",
        source_pdf(
            "invoice",
            "Neighbor Tools",
            "INV-NEIGHBOR-2",
            "PO-NEIGHBOR-002",
            [("SKU-N", 1, "10.00")],
        ),
    )
    assert invoice["matches"] == []
    assert any(f["code"] == "PO_NOT_FOUND" for f in invoice["findings"])
    assert not any(f["code"] == "AMBIGUOUS_PO" for f in invoice["findings"])
