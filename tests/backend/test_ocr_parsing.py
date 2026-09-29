import io
import struct
import zlib

import pytest
from invoicelens.db import SessionLocal
from invoicelens.extraction import (
    DemoExtractionAdapter,
    PageContent,
    SourceRasterLimitError,
    _check_raster_budget,
    _label_value,
    _ocr_layout,
    _parse_lines,
    iter_pages,
    locate_evidence,
    locate_line_evidence,
)
from invoicelens.models import Document, Vendor
from invoicelens.service import (
    _ambiguous_vendor_findings,
    _contaminated_vendor_name,
    _ocr_currency,
    _ocr_identifier,
)
from PIL import Image
from reportlab.pdfgen import canvas


def test_ocr_visual_rows_keep_real_token_offsets_and_boxes():
    rows = [
        ["Vendor:", "North", "Quay"],
        ["Invoice", "#: ", "INV-7", "Date:", "06/16/2026"],
        ["Currency:", "USP", "Due", "Date:", "07/16/2026"],
        ["POH:", "PO-7"],
        ["SKU", "DESCRIPTION", "QTY", "UNIT", "PRICE", "AMOUNT"],
        ["SKU-7", "Steel", "fitting", "2", "ea", "12.50", "25.00"],
        ["Total:", "25.00"],
    ]
    tokens = []
    for index, row in enumerate(rows):
        y = 20.0 + index * 24
        for column, value in enumerate(row):
            token = value.strip()
            tokens.append(
                {
                    "text": token,
                    "bbox": [float(column * 80), y, float(column * 80 + 50), y + 10],
                }
            )
    text, words = _ocr_layout(list(reversed(tokens)))
    page = PageContent(1, text, "scanned", 600, 800, words)
    extracted = DemoExtractionAdapter().extract([page], b"", "image/png")
    assert extracted.vendor == "North Quay"
    assert extracted.number == "INV-7"
    assert extracted.currency == "USP"
    assert extracted.po_number == "PO-7"
    assert extracted.total == "25.00"
    assert [(line.sku, line.quantity, line.amount) for line in extracted.lines] == [
        ("SKU-7", "2", "25.00")
    ]
    assert "\n" in text
    evidence = locate_evidence("USP", [page], "ocr")
    assert evidence["page_number"] == 1
    assert text[evidence["span_start"] : evidence["span_end"]] == "USP"
    assert evidence["bbox"] == [80.0, 68.0, 130.0, 78.0]


def test_ocr_partial_rows_and_credit_note_negative_amount_are_not_invented():
    text = (
        "CREDIT NOTE\n"
        "Currency: USD\n"
        "SKU DESCRIPTION QTY UNIT PRICE AMOUNT\n"
        "BELT-500 Conveyor belt section 1 m 35.77 -35.77\n"
        "SKU-2 Service kit 3 ea 10.00\n"
        "SKU-3 Pump fitting 2\n"
        "ea 8.00 16.00\n"
        "Subtotal: -19.77\n"
        "Total: -19.77"
    )
    lines = _parse_lines(text, ocr=True)
    assert [(line.sku, line.quantity, line.amount) for line in lines] == [
        ("BELT-500", "1", "-35.77"),
        ("SKU-2", "3", None),
        ("SKU-3", "2", "16.00"),
    ]
    extracted = DemoExtractionAdapter().extract(
        [PageContent(1, text, "scanned", 600, 800, [])], b"", "image/png"
    )
    assert extracted.total == "-19.77"


def test_table_footer_and_billing_address_are_not_item_rows():
    text = (
        "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT\n"
        "SKU-1 Steel fitting 2 ea 12.50 25.00\n"
        "Synthetic demo dataset | Sample document operations Page 1\n"
        "SKU DESCRIPTION QTY UNIT UNIT PRICE AMOUNT\n"
        "SKU-2 Pump fitting 2\n"
        "ea 8.00 16.00\n"
        "Bill to: Sample buyer, 420 Pier Street, Port Alder, PA 19002\n"
    )
    assert [(line.sku, line.quantity, line.amount) for line in _parse_lines(text)] == [
        ("SKU-1", "2", "25.00"),
        ("SKU-2", "2", "16.00"),
    ]


def test_scanned_header_uses_only_printed_identifier_and_adjacent_date():
    text = (
        "INVOICE\n"
        "Invoice # 011-26-0003 22.09.2026\n"
        "Currency: EUR 21.11.2026\n"
        "PO #: 2 HI-PO-00044\n"
        "Total: 497.63,\n"
    )
    extracted = DemoExtractionAdapter().extract(
        [PageContent(1, text, "scanned", 600, 800, [])], b"", "image/png"
    )
    assert extracted.number == "011-26-0003"
    assert extracted.po_number == "HI-PO-00044"
    assert extracted.date == "22.09.2026"
    assert extracted.total == "497.63"
    assert _label_value("Total: .50", [r"total"]) == ".50"
    assert (
        DemoExtractionAdapter()
        .extract(
            [
                PageContent(
                    1,
                    "INVOICE\nInvoice #: INV-7 Date: 06/16/2026\n"
                    "PO #: HI-PO-00057 4\nTotal: 6,026.90.",
                    "scanned",
                    600,
                    800,
                    [],
                )
            ],
            b"",
            "image/png",
        )
        .po_number
        == "HI-PO-00057"
    )


def test_scanned_header_cleanup_is_narrow():
    assert _ocr_currency("usp Due Date: 08/24/2026") == "USD"
    assert _ocr_currency("CAD �Due") == "CAD"
    assert _ocr_currency("XYZ") is None
    assert _ocr_identifier("�CN-00017�") == "CN-00017"
    assert _contaminated_vendor_name("North Quay Fasteners Invoice # 001-26-0002")
    assert not _contaminated_vendor_name("North Quay Fasteners")


def test_raster_budget_rejects_compressed_large_sources_before_decode_or_render():
    _check_raster_budget(4_962, 7_014, 1.0, 1)  # A4 scan at about 600 DPI.
    with pytest.raises(SourceRasterLimitError, match="reduce the scan resolution"):
        _check_raster_budget(10_000, 10_000, 2.0, 1)

    small = io.BytesIO()
    Image.new("RGB", (1, 1)).save(small, format="PNG")
    large_header = bytearray(small.getvalue())
    large_header[16:24] = struct.pack(">II", 9_000, 9_000)
    large_header[29:33] = zlib.crc32(large_header[12:29]).to_bytes(4, "big")
    with pytest.raises(SourceRasterLimitError, match="reduce the scan resolution"):
        list(iter_pages(bytes(large_header), "image/png"))

    buffer = io.BytesIO()
    document = canvas.Canvas(buffer, pagesize=(10_000, 10_000))
    document.showPage()
    document.save()
    with pytest.raises(SourceRasterLimitError, match="reduce the scan resolution"):
        list(iter_pages(buffer.getvalue(), "application/pdf"))


def test_model_page_only_evidence_never_invents_a_span_or_box():
    first = PageContent(3, "Original amount shown as 10", "native", 612, 792, [])
    second = PageContent(4, "Original amount shown as 20", "native", 612, 792, [])
    page_only = locate_evidence("ten dollars", [first], "model")
    assert page_only["page_number"] == 3
    assert page_only["span_start"] is None
    assert page_only["span_end"] is None
    assert page_only["bbox"] is None
    assert (
        locate_evidence("ten dollars", [first, second], "model")["page_number"] is None
    )
    exact = locate_evidence("20", [first, second], "model")
    assert exact["page_number"] == 4
    assert second.text[exact["span_start"] : exact["span_end"]] == "20"
    assert locate_evidence(None, [first], "model")["page_number"] is None


def test_repeated_values_use_field_label_and_distinct_line_rows():
    text = (
        "Date: 06/16/2026\n"
        "Due Date: 06/16/2026\n"
        "SKU-7 Steel fitting 1 ea 20.00 20.00\n"
        "SKU-7 Steel fitting 1 ea 20.00 20.00\n"
        "Subtotal: 20.00\n"
        "Total: 20.00"
    )
    page = PageContent(1, text, "native", 612, 792, [])
    date = locate_evidence("06/16/2026", [page], "source", "date")
    due = locate_evidence("06/16/2026", [page], "source", "due_date")
    subtotal = locate_evidence("20.00", [page], "source", "subtotal")
    total = locate_evidence("20.00", [page], "source", "total")
    assert date["span_start"] < due["span_start"]
    assert subtotal["span_start"] < total["span_start"]
    row = {
        "sku": "SKU-7",
        "description": "Steel fitting",
        "quantity": "1",
        "unit": "ea",
        "unit_price": "20.00",
        "amount": "20.00",
    }
    used_rows = set()
    first = locate_line_evidence(row, [page], "source", used_rows)
    second = locate_line_evidence(row, [page], "source", used_rows)
    assert first["sku"]["span_start"] < second["sku"]["span_start"]
    ambiguous = locate_evidence("20.00", [page], "source")
    assert ambiguous["page_number"] == 1
    assert ambiguous["span_start"] is None
    assert ambiguous["bbox"] is None


def test_vendor_alias_ignores_ocr_contaminated_candidates(client):
    with SessionLocal() as db:
        db.add_all(
            [
                Vendor(
                    workspace_id="harbor-demo-a",
                    name=name,
                    normalized_name=name.casefold(),
                )
                for name in (
                    "Sample Line Invoice # 101",
                    "Sample Line Invoice # 102",
                )
            ]
        )
        db.flush()
        document = Document(workspace_id="harbor-demo-a", kind="invoice")
        data = {"fields": {"vendor": {"value": "Sample Line", "source": "ocr"}}}
        assert _ambiguous_vendor_findings(db, document, data) == []
        db.add_all(
            [
                Vendor(
                    workspace_id="harbor-demo-a",
                    name=name,
                    normalized_name=name.casefold(),
                )
                for name in ("Sample Line East", "Sample Line West")
            ]
        )
        db.flush()
        assert (
            _ambiguous_vendor_findings(db, document, data)[0]["code"]
            == "AMBIGUOUS_VENDOR"
        )
        db.add_all(
            [
                Vendor(
                    workspace_id="harbor-demo-a",
                    name=name,
                    normalized_name=name.casefold(),
                )
                for name in ("Ridgeway Process Supply", "Ridgeway Precision Supply")
            ]
        )
        db.flush()
        data["fields"]["vendor"]["value"] = "Ridgeway Supply"
        candidates = _ambiguous_vendor_findings(db, document, data)
        assert candidates[0]["code"] == "AMBIGUOUS_VENDOR"
        assert len(candidates[0]["details"]["candidate_vendors"]) == 2
        db.rollback()
