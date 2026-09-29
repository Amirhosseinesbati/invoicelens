"""Reproducible, fully fictional InvoiceLens source-document generator.

The public manifest contains only ingest metadata. Scenario truth is written to
``evals/data`` and must never be mounted as application storage or model context.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


SEED = 20260927
DEFAULT_REFERENCE_DATE = date(2026, 9, 27)
SCHEMA_VERSION = "1.0"
DATASET_NAME = "Synthetic demo dataset"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FULL_OUTPUT = ROOT / "generated" / "invoicelens"
DEFAULT_FAST_OUTPUT = ROOT / "generated" / "invoicelens-fast"
EVAL_DATA = ROOT / "evals" / "data"

VENDOR_NAMES = (
    "North Quay Fasteners", "North Quay Fabrication", "Crescent Valve Works",
    "Morrow Pneumatics", "Cobalt Harbor Bearings", "Red Cedar Hydraulics",
    "Kestrel Conveyor Parts", "Whitecap Electrical", "Beacon Seal & Gasket",
    "Mariner Tooling", "Ridgeway Process Supply", "Ridgeway Precision Supply",
    "Pierline Safety Systems", "Mica Industrial Ceramics", "Summit Fluid Controls",
    "East Basin Instruments", "Larchstone Components", "Blue Heron Motion",
    "Aster Dock Equipment", "Copper Finch Automation",
)

PRODUCTS = (
    ("BRG-6204", "Shielded radial bearing, 20 mm bore", "ea", "18.40"),
    ("VLV-214", "Two-way stainless isolation valve", "ea", "74.25"),
    ("HSE-10M", "Reinforced hydraulic hose, 10 m coil", "roll", "92.80"),
    ("BLT-M12", "M12 zinc flange bolt, carton of 100", "box", "24.90"),
    ("GSK-EPDM", "EPDM flange gasket, DN50, packet", "box", "31.60"),
    ("SNS-PX4", "Proximity sensor with 2 m cable", "ea", "46.75"),
    ("FLT-20U", "Inline particulate filter, 20 micron", "ea", "58.30"),
    ("BELT-500", "Conveyor belt section, 500 mm width", "m", "36.50"),
    ("CPL-SS8", "Stainless coupling, 8 mm, precision bore", "ea", "12.15"),
    ("PMP-SEAL", "Pump mechanical seal service kit", "kit", "134.20"),
    ("REG-4B", "Four-port air pressure regulator", "ea", "88.95"),
    ("CAB-25", "Shielded control cable, 25 m reel", "roll", "69.40"),
    ("LMP-LED", "Industrial LED stack light, amber", "ea", "57.90"),
    ("CLP-440", "Heavy-duty rail clamp, 440 N rating", "ea", "15.80"),
    ("OIL-32", "ISO VG 32 hydraulic oil, 5 L can", "ea", "41.35"),
    ("DRV-MINI", "Compact variable-speed motor drive", "ea", "249.00"),
    ("TUB-6MM", "Polyurethane pneumatic tube, 6 mm OD", "m", "3.80"),
    ("NUT-M16", "M16 stainless lock nut, bag of 50", "box", "22.70"),
    ("BKT-90", "Right-angle mounting bracket, coated steel", "ea", "19.55"),
    ("SWX-24", "24 V maintained-contact selector switch", "ea", "44.10"),
)

ACCENTS = (
    "#2457A7", "#2D7669", "#343B48", "#A36337", "#596273", "#8A704B",
    "#9C4860", "#1D5261", "#176C6B", "#B57036", "#263F70", "#634A71",
)


def decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def money(value: Decimal, currency: str) -> Decimal:
    quantum = Decimal("1") if currency == "JPY" else Decimal("0.01")
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def money_str(value: Decimal, currency: str) -> str:
    return format(money(value, currency), "f")


def display_amount(value: str, locale: str, currency: str) -> str:
    number = decimal(value)
    decimals = 0 if currency == "JPY" else 2
    formatted = f"{number:,.{decimals}f}"
    if locale == "eu":
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    if locale == "plain":
        return formatted.replace(",", "")
    return formatted


def display_date(value: str, locale: str) -> str:
    parsed = date.fromisoformat(value)
    if locale == "eu":
        return parsed.strftime("%d.%m.%Y")
    if locale == "us":
        return parsed.strftime("%m/%d/%Y")
    return parsed.isoformat()


def vendor_record(index: int) -> dict[str, str]:
    return {
        "id": f"V-{index + 1:03d}",
        "name": VENDOR_NAMES[index],
        "address": f"{110 + index * 17} Dockside Avenue, Port Alder, PA 19{index + 10:03d}",
        "email": f"billing{index + 1:02d}@example.test",
        "tax_id": f"FICTIONAL-TAX-{index + 1:04d}",
    }


def product_record(product: tuple[str, str, str, str], qty: int, unit_price: Decimal, currency: str) -> dict[str, str]:
    sku, description, unit, _ = product
    return {
        "sku": sku,
        "description": description,
        "quantity": str(qty),
        "unit": unit,
        "unit_price": money_str(unit_price, currency),
        "line_amount": money_str(money(decimal(qty) * unit_price, currency), currency),
    }


def financials(lines: list[dict[str, str]], currency: str, tax_rate: Decimal, freight: Decimal, discount: Decimal, total_offset: Decimal = Decimal("0")) -> dict[str, str]:
    subtotal = money(sum((decimal(row["line_amount"]) for row in lines), Decimal("0")), currency)
    tax = money((subtotal - discount) * tax_rate, currency)
    computed_total = money(subtotal + tax + freight - discount, currency)
    printed_total = money(computed_total + total_offset, currency)
    return {
        "subtotal": money_str(subtotal, currency),
        "tax_rate": str(tax_rate),
        "tax": money_str(tax, currency),
        "freight": money_str(freight, currency),
        "discount": money_str(discount, currency),
        "total": money_str(printed_total, currency),
        "computed_total": money_str(computed_total, currency),
    }


def build_scenarios(seed: int, reference_date: date) -> list[dict[str, Any]]:
    """Build complete source truth before drawing a single document."""
    rng = random.Random(seed)
    documents: list[dict[str, Any]] = []
    invoice_counter = 0
    po_counter = 0
    credit_counter = 0
    for vi in range(20):
        vendor = vendor_record(vi)
        workspace = "harbor-demo-a" if vi < 10 else "harbor-demo-b"
        layout_id = (vi % 8) + 1 if vi < 16 else vi - 7  # 1-8 dev, 9-12 held out
        split = "development" if vi < 16 else "held_out"
        currency = ("USD", "EUR", "GBP", "CAD", "JPY")[vi % 5]
        locale = ("us", "eu", "plain")[vi % 3]
        po_sources: list[dict[str, Any]] = []
        for pi in range(3):
            po_counter += 1
            po_date = reference_date - timedelta(days=130 - pi * 34 - vi % 7)
            chosen = rng.sample(PRODUCTS, 8)
            lines = [
                product_record(product, rng.randint(24, 90), money(decimal(product[3]) * (Decimal("1") + decimal((vi % 5) - 2) / Decimal("100")), currency), currency)
                for product in chosen
            ]
            source: dict[str, Any] = {
                "vendor": vendor,
                "printed_vendor_name": vendor["name"],
                "number": f"HI-PO-{po_counter:05d}",
                "date": po_date.isoformat(),
                "due_date": (po_date + timedelta(days=45)).isoformat(),
                "currency": currency,
                "po_number": None,
                "lines": lines,
                **financials(lines, currency, Decimal("0"), Decimal("0"), Decimal("0")),
            }
            po_sources.append(source)
            documents.append({
                "id": f"PO-{po_counter:04d}", "workspace": workspace,
                "vendor_id": vendor["id"], "type": "purchase_order",
                "layout_id": layout_id, "split": split, "locale": locale,
                "source": source, "expected_findings": [],
            })

        vendor_invoices: list[dict[str, Any]] = []
        for ii in range(11):
            invoice_counter += 1
            index = invoice_counter - 1
            po = po_sources[ii % 3]
            inv_date = date.fromisoformat(po["date"]) + timedelta(days=12 + ii * 5 + vi % 4)
            due_date = inv_date + timedelta(days=(30, 45, 60)[ii % 3])
            missing_po = index % 19 == 4
            line_count = 14 if ii == 6 else rng.randint(4, 7)
            po_lines = po["lines"]
            selected = [po_lines[n % len(po_lines)] for n in rng.sample(range(len(po_lines)), min(line_count, len(po_lines)))]
            if line_count > len(selected):
                selected += [po_lines[n % len(po_lines)] for n in range(line_count - len(selected))]
            # Repeated SKUs can appear in multi-page partial-shipment rows; line order is material.
            lines: list[dict[str, str]] = []
            labels: list[dict[str, Any]] = []
            for li, original in enumerate(selected):
                qty = rng.randint(1, 9)
                price = decimal(original["unit_price"])
                if li == 0 and index % 15 == 5 and not missing_po:
                    qty = int(original["quantity"]) + 5
                    labels.append({"kind": "quantity_mismatch", "line_index": li, "po_number": po["number"]})
                if li == 0 and index % 13 == 3 and not missing_po:
                    price = money(price * Decimal("1.18"), currency)
                    labels.append({"kind": "unit_price_mismatch", "line_index": li, "po_number": po["number"]})
                product = next(product for product in PRODUCTS if product[0] == original["sku"])
                row = product_record(product, qty, price, currency)
                if ii == 6 and li % 4 == 1:
                    row["description"] += " - compatible with older service kits, revision B"
                lines.append(row)
            tax_rate = (Decimal("0"), Decimal("0.07"), Decimal("0.0825"), Decimal("0.19"))[(vi + ii) % 4]
            freight = money(decimal(rng.choice((0, 0, 0, 12, 18, 25))), currency)
            discount = money(decimal(rng.choice((0, 0, 0, 5, 10, 15))), currency)
            offset = money(Decimal("17.40"), currency) if index % 17 == 7 else Decimal("0")
            if offset:
                labels.append({"kind": "total_inconsistent", "difference": money_str(offset, currency)})
            if missing_po:
                po_number = f"HI-PO-MISSING-{invoice_counter:05d}"
                labels.append({"kind": "po_missing", "po_number": po_number})
            else:
                po_number = po["number"]
            if ii == 8:
                invoice_number = vendor_invoices[2]["source"]["number"]
                labels.append({"kind": "duplicate_invoice", "duplicate_of": vendor_invoices[2]["id"]})
            else:
                invoice_number = f"{vendor['id'][-3:]}-{reference_date.year % 100:02d}-{ii + 1:04d}"
            printed_vendor = vendor["name"]
            if vi in (0, 1, 10, 11) and ii == 9:
                printed_vendor = "North Quay" if vi < 2 else "Ridgeway Supply"
                labels.append({"kind": "ambiguous_vendor_match", "candidate_vendor_ids": ["V-001", "V-002"] if vi < 2 else ["V-011", "V-012"]})
            source = {
                "vendor": vendor,
                "printed_vendor_name": printed_vendor,
                "number": invoice_number,
                "date": inv_date.isoformat(),
                "due_date": due_date.isoformat(),
                "currency": currency,
                "po_number": po_number,
                "lines": lines,
                **financials(lines, currency, tax_rate, freight, discount, offset),
            }
            # Distinct invoice IDs with the same date, amount and PO are clean hard negatives.
            if ii == 10:
                clean_twin = next(item["source"] for item in vendor_invoices if not item["expected_findings"])
                source.update({key: clean_twin[key] for key in ("date", "due_date", "po_number", "lines", "subtotal", "tax_rate", "tax", "freight", "discount", "total", "computed_total")})
                labels = []
            scenario = {
                "id": f"INV-{invoice_counter:04d}", "workspace": workspace,
                "vendor_id": vendor["id"], "type": "invoice",
                "layout_id": layout_id, "split": split, "locale": locale,
                "source": source, "expected_findings": labels,
                "lookalike_legitimate": ii == 10,
            }
            documents.append(scenario)
            vendor_invoices.append(scenario)

        credit_counter += 1
        original = vendor_invoices[0]["source"]
        credited = original["lines"][0]
        credit_line = dict(credited)
        credit_line["quantity"] = "-1"
        credit_line["line_amount"] = money_str(-decimal(credited["unit_price"]), currency)
        credit_date = date.fromisoformat(original["date"]) + timedelta(days=32)
        credit_source = {
            "vendor": vendor,
            "printed_vendor_name": vendor["name"],
            "number": f"CN-{credit_counter:05d}",
            "date": credit_date.isoformat(),
            "due_date": credit_date.isoformat(),
            "currency": currency,
            "po_number": original["po_number"],
            "reference_invoice": original["number"],
            "lines": [credit_line],
            **financials([credit_line], currency, Decimal("0"), Decimal("0"), Decimal("0")),
        }
        documents.append({
            "id": f"CRN-{credit_counter:04d}", "workspace": workspace,
            "vendor_id": vendor["id"], "type": "credit_note",
            "layout_id": layout_id, "split": split, "locale": locale,
            "source": credit_source, "expected_findings": [],
        })

    assert Counter(d["type"] for d in documents) == {"invoice": 220, "purchase_order": 60, "credit_note": 20}
    assert 900 <= sum(len(d["source"]["lines"]) for d in documents if d["type"] == "invoice") <= 1500
    return documents


def select_fast(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    invoices = [d for d in scenarios if d["type"] == "invoice"]
    desired = ("unit_price_mismatch", "quantity_mismatch", "total_inconsistent", "po_missing")
    chosen: list[dict[str, Any]] = []
    used_vendors: set[str] = set()
    scan_ids = {d["id"] for index, d in enumerate(scenarios) if index % 10 in (1, 4, 8)}
    for finding in desired:
        match = next(
            d for d in invoices
            if finding in {f["kind"] for f in d["expected_findings"]}
            and d["vendor_id"] not in used_vendors
            and (finding != "quantity_mismatch" or d["id"] in scan_ids)
        )
        chosen.append(match)
        used_vendors.add(match["vendor_id"])
    clean = next(d for d in invoices if not d["expected_findings"] and d["vendor_id"] not in used_vendors and d["lookalike_legitimate"])
    chosen.append(clean)
    po_numbers = {d["source"]["po_number"] for d in chosen}
    support = [d for d in scenarios if d["type"] == "purchase_order" and d["source"]["number"] in po_numbers]
    ids = {d["id"] for d in chosen + support}
    return [d for d in scenarios if d["id"] in ids]


def rgb(hex_color: str) -> colors.Color:
    return colors.HexColor(hex_color)


def draw_text(c: canvas.Canvas, x: float, y: float, value: str, *, size: int = 9, bold: bool = False, color: colors.Color = colors.HexColor("#28313A")) -> None:
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(value))


def wrap_text(value: str, font: str, size: int, max_width: float) -> list[str]:
    words = value.split()
    if not words:
        return [""]
    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        candidate = f"{line} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def draw_page_header(c: canvas.Canvas, scenario: dict[str, Any], width: float, height: float, page_number: int) -> float:
    layout = scenario["layout_id"]
    source = scenario["source"]
    accent = rgb(ACCENTS[layout - 1])
    ink = rgb("#27313A")
    soft = rgb("#F5F3EE")
    margin = 42
    title = {"invoice": "INVOICE", "purchase_order": "PURCHASE ORDER", "credit_note": "CREDIT NOTE"}[scenario["type"]]
    if layout == 9:
        c.setFillColor(accent)
        c.rect(0, 0, 10, height, fill=1, stroke=0)
        draw_text(c, margin, height - 55, title, size=25, bold=True, color=accent)
        draw_text(c, width - 240, height - 48, source["printed_vendor_name"].upper(), size=11, bold=True)
        draw_text(c, width - 240, height - 66, source["vendor"]["address"], size=7)
        c.setStrokeColor(accent)
        c.setLineWidth(3)
        c.line(margin, height - 92, width - margin, height - 92)
        y = height - 118
    elif layout == 10:
        c.setFillColor(accent)
        c.roundRect(margin - 4, height - 105, 228, 76, 8, fill=1, stroke=0)
        draw_text(c, margin + 10, height - 61, title, size=16, bold=True, color=colors.white)
        draw_text(c, width - 276, height - 53, source["printed_vendor_name"], size=12, bold=True)
        draw_text(c, width - 276, height - 72, source["vendor"]["address"], size=7)
        c.setFillColor(accent)
        c.rect(width - 18, 0, 18, height, fill=1, stroke=0)
        y = height - 130
    elif layout == 11:
        c.setFillColor(accent)
        c.rect(0, height - 22, width, 22, fill=1, stroke=0)
        draw_text(c, width / 2 - 125, height - 58, source["printed_vendor_name"], size=13, bold=True)
        draw_text(c, width / 2 - 125, height - 75, source["vendor"]["address"], size=7)
        draw_text(c, margin, height - 109, title, size=18, bold=True, color=accent)
        c.setStrokeColor(accent)
        c.setLineWidth(1)
        c.roundRect(width - 224, height - 119, 182, 27, 5, fill=0, stroke=1)
        draw_text(c, width - 214, height - 110, source["number"], size=10, bold=True)
        y = height - 143
    elif layout == 12:
        c.setFillColor(soft)
        c.rect(0, height - 126, width, 126, fill=1, stroke=0)
        c.setFillColor(accent)
        c.rect(0, height - 126, width, 9, fill=1, stroke=0)
        draw_text(c, margin, height - 49, title, size=24, bold=True, color=accent)
        draw_text(c, margin, height - 80, source["printed_vendor_name"], size=12, bold=True)
        draw_text(c, margin, height - 100, source["vendor"]["address"], size=8)
        y = height - 151
    elif layout in (1, 5):
        c.setFillColor(accent)
        c.rect(0, height - 118, width, 118, fill=1, stroke=0)
        draw_text(c, margin, height - 50, source["printed_vendor_name"], size=17, bold=True, color=colors.white)
        draw_text(c, width - 190, height - 49, title, size=17, bold=True, color=colors.white)
        draw_text(c, margin, height - 78, source["vendor"]["address"], size=8, color=colors.white)
        y = height - 143
    elif layout in (2, 6):
        c.setFillColor(accent)
        c.rect(0, 0, 13, height, fill=1, stroke=0)
        draw_text(c, margin, height - 48, source["printed_vendor_name"], size=17, bold=True, color=ink)
        draw_text(c, margin, height - 70, source["vendor"]["address"], size=8)
        draw_text(c, width - 200, height - 49, title, size=15, bold=True, color=accent)
        c.setStrokeColor(accent)
        c.setLineWidth(2)
        c.line(margin, height - 92, width - margin, height - 92)
        y = height - 120
    elif layout in (3, 7):
        c.setFillColor(soft)
        c.roundRect(margin - 10, height - 114, width - 2 * margin + 20, 83, 7, fill=1, stroke=0)
        draw_text(c, margin, height - 56, title, size=22, bold=True, color=accent)
        draw_text(c, margin, height - 79, source["printed_vendor_name"], size=10, bold=True)
        draw_text(c, width - 250, height - 79, source["vendor"]["address"], size=7)
        y = height - 136
    else:
        draw_text(c, margin, height - 47, source["printed_vendor_name"].upper(), size=12, bold=True, color=accent)
        draw_text(c, margin, height - 66, source["vendor"]["address"], size=8)
        draw_text(c, width - 190, height - 47, title, size=17, bold=True, color=ink)
        c.setStrokeColor(accent)
        c.setLineWidth(1.5)
        c.line(margin, height - 84, width - margin, height - 84)
        y = height - 114
    label_x = margin
    value_x = margin + 94
    right_label_x = width / 2 + 20
    right_value_x = right_label_x + 83
    draw_text(c, label_x, y, "Vendor:", size=8, color=rgb("#66717B"))
    draw_text(c, label_x + 57, y, source["printed_vendor_name"], size=9, bold=True)
    y -= 20
    number_label = {"invoice": "Invoice #:", "purchase_order": "Purchase Order #:", "credit_note": "Credit Note #:"}[scenario["type"]]
    rows = [
        (number_label, source["number"], "Date:", display_date(source["date"], scenario["locale"])),
        ("Currency:", source["currency"], "Due Date:" if scenario["type"] != "purchase_order" else "Delivery Date:", display_date(source["due_date"], scenario["locale"])),
        ("PO #:", source["po_number"] or "-", "Page:", str(page_number)),
    ]
    if scenario["type"] == "credit_note":
        rows[2] = ("Reference:", source["reference_invoice"], "PO #:", source["po_number"] or "-")
    for left_label, left_value, right_label, right_value in rows:
        draw_text(c, label_x, y, left_label, size=8, color=rgb("#66717B"))
        draw_text(c, value_x, y, left_value, size=9, bold=True)
        draw_text(c, right_label_x, y, right_label, size=8, color=rgb("#66717B"))
        draw_text(c, right_value_x, y, right_value, size=9, bold=True)
        y -= 20
    y -= 13
    c.setFillColor(accent if layout % 2 else rgb("#E9EDF0"))
    c.rect(margin, y - 10, width - 2 * margin, 27, fill=1, stroke=0)
    table_color = colors.white if layout % 2 else ink
    for x, label in ((margin + 7, "SKU"), (margin + 91, "DESCRIPTION"), (width - 220, "QTY"), (width - 177, "UNIT"), (width - 154, "UNIT PRICE"), (width - 82, "AMOUNT")):
        draw_text(c, x, y, label, size=7, bold=True, color=table_color)
    return y - 21


def draw_footer(c: canvas.Canvas, scenario: dict[str, Any], width: float, page_number: int) -> None:
    c.setStrokeColor(rgb("#D4D9DC"))
    c.setLineWidth(0.6)
    c.line(42, 45, width - 42, 45)
    draw_text(c, 42, 31, "Synthetic demo dataset  |  Harbor Industrial document operations", size=7, color=rgb("#87919A"))
    draw_text(c, width - 80, 31, f"Page {page_number}", size=7, color=rgb("#87919A"))


def render_pdf(scenario: dict[str, Any], output: Path) -> int:
    source = scenario["source"]
    layout = scenario["layout_id"]
    page_size = A4 if layout in (2, 4, 6, 8, 10, 12) else letter
    width, height = page_size
    c = canvas.Canvas(str(output), pagesize=page_size, pageCompression=1)
    c.setTitle(f"{source['number']} - Synthetic demo dataset")
    c.setAuthor("Harbor Industrial (fictional)")
    page = 1
    y = draw_page_header(c, scenario, width, height, page)
    accent = rgb(ACCENTS[layout - 1])
    for li, line in enumerate(source["lines"]):
        description = wrap_text(line["description"], "Helvetica", 8, width - 360)
        row_height = max(27, 12 + len(description) * 10)
        if y - row_height < 140:
            draw_footer(c, scenario, width, page)
            c.showPage()
            page += 1
            y = draw_page_header(c, scenario, width, height, page)
        if (li + layout) % 2 == 0:
            c.setFillColor(rgb("#F6F7F7"))
            c.rect(42, y - row_height + 8, width - 84, row_height, fill=1, stroke=0)
        draw_text(c, 49, y - 5, line["sku"], size=8, bold=True, color=accent)
        for di, part in enumerate(description):
            draw_text(c, 133, y - 5 - di * 10, part, size=8)
        draw_text(c, width - 219, y - 5, line["quantity"], size=8)
        draw_text(c, width - 177, y - 5, line["unit"], size=8)
        draw_text(c, width - 154, y - 5, display_amount(line["unit_price"], scenario["locale"], source["currency"]), size=8)
        draw_text(c, width - 82, y - 5, display_amount(line["line_amount"], scenario["locale"], source["currency"]), size=8)
        y -= row_height
    if y < 178:
        draw_footer(c, scenario, width, page)
        c.showPage()
        page += 1
        y = draw_page_header(c, scenario, width, height, page)
    y -= 8
    c.setStrokeColor(accent)
    c.setLineWidth(1)
    c.line(width - 246, y + 12, width - 42, y + 12)
    labels = (("Subtotal:", "subtotal"), ("Discount:", "discount"), ("Tax:", "tax"), ("Freight:", "freight"), ("Total:", "total"))
    for label, key in labels:
        bold = key == "total"
        draw_text(c, width - 235, y, label, size=9 if bold else 8, bold=bold)
        draw_text(c, width - 119, y, display_amount(source[key], scenario["locale"], source["currency"]), size=9 if bold else 8, bold=bold, color=accent if bold else rgb("#27313A"))
        y -= 18
    draw_text(c, 42, 75, "Bill to: Harbor Industrial, 420 Pier Street, Port Alder, PA 19002", size=8)
    draw_text(c, 42, 62, f"Questions: {source['vendor']['email']}  |  Tax ID: {source['vendor']['tax_id']}", size=7, color=rgb("#66717B"))
    draw_footer(c, scenario, width, page)
    c.save()
    return page


def degrade_image(image: Image.Image, rng: random.Random, intensity: str) -> Image.Image:
    image = image.convert("RGB")
    angle = rng.uniform(-0.75, 0.75) if intensity == "mild" else rng.uniform(-1.4, 1.4)
    image = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
    image = ImageEnhance.Contrast(image).enhance(0.88 if intensity == "mild" else 0.73)
    image = image.filter(ImageFilter.GaussianBlur(radius=0.25 if intensity == "mild" else 0.48))
    # Coarse paper-noise specks remain reproducible without obscuring characters.
    pixels = image.load()
    width, height = image.size
    for _ in range((width * height) // (950 if intensity == "mild" else 520)):
        x, y = rng.randrange(width), rng.randrange(height)
        shade = rng.randint(174, 222)
        pixels[x, y] = (shade, shade, shade)
    return image


def rasterize_document(native_pdf: Path, target: Path, medium: str, rng: random.Random, damaged: bool, temp_root: Path | None = None) -> None:
    converter = shutil.which("pdftoppm")
    if not converter:
        raise RuntimeError("pdftoppm (Poppler) is required to produce the scanned dataset")
    with tempfile.TemporaryDirectory(prefix="invoicelens-render-", dir=temp_root) as temporary:
        prefix = Path(temporary) / "page"
        result = subprocess.run([converter, "-r", "125", "-png", str(native_pdf), str(prefix)], capture_output=True, text=True, timeout=90, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Poppler failed for {native_pdf.name}: {result.stderr.strip()}")
        pages = sorted(Path(temporary).glob("page-*.png"))
        if not pages:
            raise RuntimeError(f"No raster pages for {native_pdf.name}")
        altered = [degrade_image(Image.open(path), rng, "strong" if damaged else "mild") for path in pages]
        if medium in ("png", "jpeg") and len(altered) == 1:
            altered[0].save(target, format="PNG" if medium == "png" else "JPEG", quality=83)
            return
        # A scanned PDF contains only page-sized image XObjects, no native text.
        pdf = canvas.Canvas(str(target), pagesize=letter, pageCompression=1)
        for image in altered:
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=82, optimize=True)
            buffer.seek(0)
            pdf.setPageSize((image.width * 72 / 125, image.height * 72 / 125))
            pdf.drawImage(ImageReader(buffer), 0, 0, width=image.width * 72 / 125, height=image.height * 72 / 125)
            pdf.showPage()
        pdf.save()


def render_dataset(scenarios: list[dict[str, Any]], output: Path, seed: int, reference_date: date, preset: str, truth_output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    docs_dir = output / "documents"
    docs_dir.mkdir(exist_ok=True)
    previous_paths: set[str] = set()
    previous_manifest = output / "manifest.json"
    if previous_manifest.exists():
        old = json.loads(previous_manifest.read_text(encoding="utf-8"))
        previous_paths = {str(item.get("path", "")) for item in old.get("documents", [])}
    rng = random.Random(seed + 321)
    manifest_documents: list[dict[str, str]] = []
    # Scan assignment follows the stable full-corpus index.
    all_docs = build_scenarios(seed, reference_date)
    scan_ordinals = {d["id"]: ordinal for ordinal, d in enumerate(d for index, d in enumerate(all_docs) if index % 10 in (1, 4, 8))}
    for number, scenario in enumerate(scenarios, 1):
        doc_id = scenario["id"]
        scan_ordinal = scan_ordinals.get(doc_id)
        scanned = scan_ordinal is not None
        medium = "pdf"
        if scanned:
            mod = scan_ordinal % 15
            medium = "png" if mod in (0, 1, 2) else "jpeg" if mod in (3, 4) else "pdf"
        with tempfile.TemporaryDirectory(prefix="invoicelens-source-", dir=output) as temporary:
            native = Path(temporary) / f"{doc_id}.pdf"
            page_count = render_pdf(scenario, native)
            if page_count > 1:
                medium = "pdf"
            suffix = ".jpg" if medium == "jpeg" else f".{medium}"
            target = docs_dir / f"{doc_id}{suffix}"
            if scanned:
                rasterize_document(native, target, medium, rng, damaged=(scan_ordinal % 19 == 7 or preset == "fast"), temp_root=output)
            else:
                shutil.copyfile(native, target)
        scenario["render"] = {
            "path": f"documents/{target.name}", "medium": medium,
            "scanned": scanned, "page_count": page_count,
        }
        scenario["overlapping_case"] = len(scenario["expected_findings"]) > 1
        manifest_documents.append({
            "id": doc_id, "workspace": scenario["workspace"],
            "vendor_id": scenario["vendor_id"], "type": scenario["type"],
            "path": f"documents/{target.name}",
        })
        if number % 25 == 0 or number == len(scenarios):
            print(f"Rendered {number}/{len(scenarios)} documents", flush=True)
    manifest = {
        "schema_version": SCHEMA_VERSION, "dataset": DATASET_NAME,
        "seed": seed, "reference_date": reference_date.isoformat(),
        "documents": manifest_documents,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    current_paths = {item["path"] for item in manifest_documents}
    for old_path in previous_paths - current_paths:
        stale = output / old_path
        if stale.parent.resolve() == docs_dir.resolve() and stale.is_file():
            stale.unlink()
    truth_output.parent.mkdir(parents=True, exist_ok=True)
    truth = {
        "schema_version": SCHEMA_VERSION, "dataset": DATASET_NAME,
        "seed": seed, "reference_date": reference_date.isoformat(), "preset": preset,
        "documents": scenarios,
    }
    truth_output.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return truth


def inventory(truth: dict[str, Any]) -> dict[str, Any]:
    docs = truth["documents"]
    invoices = [d for d in docs if d["type"] == "invoice"]
    return {
        "documents": len(docs),
        "types": dict(Counter(d["type"] for d in docs)),
        "vendors": len({d["vendor_id"] for d in docs}),
        "layouts": len({d["layout_id"] for d in docs}),
        "held_out_layouts": sorted({d["layout_id"] for d in docs if d["split"] == "held_out"}),
        "invoice_lines": sum(len(d["source"]["lines"]) for d in invoices),
        "scanned": sum(d["render"]["scanned"] for d in docs),
        "multi_page": sum(d["render"]["page_count"] > 1 for d in docs),
        "findings": dict(Counter(f["kind"] for d in docs for f in d["expected_findings"])),
        "overlapping_documents": sum(d["overlapping_case"] for d in docs),
        "legitimate_lookalikes": sum(d.get("lookalike_legitimate", False) for d in docs),
    }


def rerender_credit_notes(scenarios: list[dict[str, Any]], output: Path, seed: int, reference_date: date) -> int:
    """Repair only credit-note source files, preserving manifest, truth and other PDFs."""
    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Full manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("seed") != seed or manifest.get("reference_date") != reference_date.isoformat():
        raise ValueError("Existing manifest seed/reference date differ from requested regeneration")
    entries = {item["id"]: item for item in manifest["documents"]}
    credit_notes = [(index, scenario) for index, scenario in enumerate(scenarios) if scenario["type"] == "credit_note"]
    if len(credit_notes) != 20 or len(entries) != 300:
        raise ValueError("Selective credit-note rendering requires the complete 300-document manifest")
    docs_dir = (output / "documents").resolve()
    scan_ordinals = {scenario["id"]: ordinal for ordinal, scenario in enumerate(item for index, item in enumerate(scenarios) if index % 10 in (1, 4, 8))}
    for index, scenario in credit_notes:
        entry = entries[scenario["id"]]
        target = (output / entry["path"]).resolve()
        if target.parent != docs_dir or not target.is_file() or entry["type"] != "credit_note":
            raise ValueError(f"Unsafe or missing credit-note source path: {entry['path']}")
        scanned = scenario["id"] in scan_ordinals
        medium = "jpeg" if target.suffix.lower() in (".jpg", ".jpeg") else target.suffix.lower().lstrip(".")
        with tempfile.TemporaryDirectory(prefix="invoicelens-credit-", dir=output) as temporary:
            native = Path(temporary) / f"{scenario['id']}.pdf"
            render_pdf(scenario, native)
            if scanned:
                ordinal = scan_ordinals[scenario["id"]]
                # The selective repair is deterministic; its paper noise may differ
                # from a fresh full run, while visible scenario facts are identical.
                rasterize_document(native, target, medium, random.Random(seed + 321 + index),
                                   damaged=ordinal % 19 == 7, temp_root=output)
            else:
                shutil.copyfile(native, target)
    return len(credit_notes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("fast", "full"), default="full")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--reference-date", type=date.fromisoformat, default=DEFAULT_REFERENCE_DATE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--truth-output", type=Path)
    parser.add_argument("--rerender-credit-notes", action="store_true", help="Repair only the 20 credit-note files in an existing full corpus")
    args = parser.parse_args()
    scenarios = build_scenarios(args.seed, args.reference_date)
    if args.preset == "fast":
        scenarios = select_fast(scenarios)
    output = (args.output or (DEFAULT_FAST_OUTPUT if args.preset == "fast" else DEFAULT_FULL_OUTPUT)).resolve()
    truth_output = (args.truth_output or (EVAL_DATA / f"{args.preset}_ground_truth.json")).resolve()
    if args.rerender_credit_notes:
        if args.preset != "full":
            parser.error("Selective credit-note rendering requires --preset full")
        count = rerender_credit_notes(scenarios, output, args.seed, args.reference_date)
        print(json.dumps({"rerendered_credit_notes": count, "manifest_unchanged": str(output / "manifest.json"),
                          "truth_unchanged": str(truth_output)}, indent=2))
        return
    if output == truth_output or truth_output.is_relative_to(output):
        parser.error("Ground truth must remain outside the public document directory")
    truth = render_dataset(scenarios, output, args.seed, args.reference_date, args.preset, truth_output)
    print(json.dumps({"manifest": str(output / "manifest.json"), "ground_truth": str(truth_output), "inventory": inventory(truth)}, indent=2))


if __name__ == "__main__":
    main()
