import copy
import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, cast

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .extraction import PageContent, locate_evidence, locate_line_evidence
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
    User,
    Vendor,
    utcnow,
)
from .rules import amount, content_hash, normalize_field, quantize, validate_arithmetic
from .storage import digest, safe_filename, save_export, save_source, storage_path, validate_upload

FIELD_KEYS = [
    "vendor",
    "number",
    "po_number",
    "date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "freight",
    "discounts",
    "total",
]


def normalize_configured(key: str, value: str | None, currency: str | None = None) -> str | None:
    settings = get_settings()
    return normalize_field(key, value, currency, settings.date_order, settings.decimal_separator)


def _ocr_currency(value: str | None) -> str | None:
    if not value:
        return None
    token = re.match(r"\s*([A-Za-z0-9]{3})", value)
    candidate = token.group(1).upper() if token else value.strip()
    # Tesseract commonly confuses the final D in a printed USD with P or O.
    candidate = {"USP": "USD", "USO": "USD", "US0": "USD"}.get(candidate, candidate)
    return normalize_configured("currency", candidate)


def _ocr_identifier(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", value)
    return cleaned or None


def _contaminated_vendor_name(value: str | None) -> bool:
    return bool(
        value
        and re.search(
            r"\b(?:invoice|credit\s+note|purchase\s+order|po)\s*(?:#|no\.?|number)"
            r"|\b(?:due\s+date|date|currency|subtotal|total)\s*[:#]",
            value,
            re.I,
        )
    )


def get_document(db: Session, workspace_id: str, document_id: str) -> Document:
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if not document:
        raise HTTPException(404, "Document not found")
    return document


def get_job(db: Session, workspace_id: str, job_id: str) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def add_event(db: Session, job: Job, event_type: str, message: str) -> None:
    db.add(
        JobEvent(
            workspace_id=job.workspace_id,
            job_id=job.id,
            type=event_type,
            message=message,
            progress=job.progress,
        )
    )
    job.updated_at = utcnow()
    db.commit()


def upload_document(
    db: Session, workspace_id: str, filename: str, content: bytes
) -> tuple[Document, Job, bool]:
    mime, extension = validate_upload(content)
    sha = digest(content)
    existing = db.scalar(
        select(Document).where(Document.workspace_id == workspace_id, Document.sha256 == sha)
    )
    if existing:
        job = db.scalar(
            select(Job)
            .where(Job.workspace_id == workspace_id, Job.document_id == existing.id)
            .order_by(Job.created_at.desc())
        )
        if job is None:
            job = Job(
                workspace_id=workspace_id, document_id=existing.id, status="complete", progress=100
            )
            db.add(job)
            db.commit()
        return existing, job, True
    key = save_source(workspace_id, content, extension)
    document = Document(
        workspace_id=workspace_id,
        filename=safe_filename(filename),
        content_type=mime,
        storage_key=key,
        sha256=sha,
    )
    db.add(document)
    db.flush()
    job = Job(workspace_id=workspace_id, document_id=document.id)
    db.add(job)
    db.commit()
    add_event(db, job, "queued", "Document queued for processing")
    return document, job, False


def version_row(db: Session, document: Document) -> ExtractionVersion | None:
    if document.version == 0:
        return None
    return db.scalar(
        select(ExtractionVersion).where(
            ExtractionVersion.document_id == document.id,
            ExtractionVersion.version == document.version,
        )
    )


def page_record(page: DocumentPage) -> dict:
    return {
        "page_number": page.page_number,
        "text": page.text,
        "source_type": page.source_type,
        "width": float(page.width),
        "height": float(page.height),
    }


def finding_record(finding: Finding) -> dict:
    return {
        "id": finding.id,
        "code": finding.code,
        "severity": finding.severity,
        "message": finding.message,
        "status": finding.status,
        "details": finding.details,
    }


def job_record(job: Job) -> dict:
    return {
        "id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "current_page": job.current_page,
        "total_pages": job.total_pages,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def summary(db: Session, document: Document) -> dict:
    count = (
        db.scalar(
            select(func.count(Finding.id)).where(
                Finding.document_id == document.id,
                Finding.extraction_version == document.version,
                Finding.status == "open",
            )
        )
        or 0
    )
    return {
        "id": document.id,
        "filename": document.filename,
        "kind": document.kind,
        "status": document.status,
        "vendor": document.vendor.name if document.vendor else None,
        "number": document.number,
        "date": document.date,
        "currency": document.currency,
        "total": document.total,
        "version": document.version,
        "page_count": len(document.pages),
        "findings_count": count,
        "created_at": document.created_at,
    }


def _line_match_candidates(db: Session, data: dict, matches: Sequence[MatchProposal]) -> list[dict]:
    chosen = next((match for match in matches if match.status in {"selected", "matched"}), None)
    if not chosen:
        return []
    po_lines = db.scalars(
        select(POLine).where(POLine.po_id == chosen.po_id).order_by(POLine.position)
    ).all()
    by_sku: dict[str, list[POLine]] = defaultdict(list)
    for line in po_lines:
        if line.sku:
            by_sku[line.sku.casefold()].append(line)
    result = []
    for index, invoice_line in enumerate(data.get("lines", [])):
        sku = invoice_line.get("sku")
        candidates = by_sku.get(sku.casefold(), []) if sku else []
        if len(candidates) <= 1:
            continue
        result.append(
            {
                "invoice_line_index": index,
                "sku": sku,
                "candidates": [
                    {
                        "po_line_id": line.id,
                        "description": line.description,
                        "quantity": line.quantity,
                        "unit_price": line.unit_price,
                        "amount": line.amount,
                    }
                    for line in candidates
                ],
            }
        )
    return result


def detail(db: Session, document: Document) -> dict:
    latest = version_row(db, document)
    findings = db.scalars(
        select(Finding)
        .where(Finding.document_id == document.id, Finding.extraction_version == document.version)
        .order_by(Finding.severity, Finding.code)
    ).all()
    matches = db.scalars(
        select(MatchProposal)
        .where(
            MatchProposal.document_id == document.id,
            MatchProposal.extraction_version == document.version,
        )
        .order_by(MatchProposal.score.desc())
    ).all()
    history = db.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.document_id == document.id)
        .order_by(ReviewDecision.created_at.desc())
    ).all()
    po_ids = [m.po_id for m in matches]
    po_by_id = (
        {
            po.id: po
            for po in db.scalars(select(PurchaseOrder).where(PurchaseOrder.id.in_(po_ids))).all()
        }
        if po_ids
        else {}
    )
    return {
        **summary(db, document),
        "pages": [page_record(page) for page in document.pages],
        "fields": latest.data.get("fields", {}) if latest else {},
        "lines": [{"id": str(i), **line} for i, line in enumerate(latest.data.get("lines", []))]
        if latest
        else [],
        "findings": [finding_record(f) for f in findings],
        "matches": [
            {
                "po_id": m.po_id,
                "document_id": po_by_id[m.po_id].document_id if m.po_id in po_by_id else None,
                "po_number": po_by_id[m.po_id].po_number if m.po_id in po_by_id else None,
                "score": float(m.score),
                "status": m.status,
                "details": m.details,
            }
            for m in matches
        ],
        "match_resolution": latest.data.get("match_resolution") if latest else None,
        "line_matches": latest.data.get("line_matches", {}) if latest else {},
        "line_match_candidates": _line_match_candidates(db, latest.data, matches) if latest else [],
        "history": [
            {
                "id": h.id,
                "action": h.action,
                "note": h.note,
                "before": h.before,
                "after": h.after,
                "version": h.extraction_version,
                "created_at": h.created_at,
            }
            for h in history
        ],
        "approval": {
            "version": document.approved_version,
            "hash": document.approved_hash,
            "approved_by": document.approved_by,
            "approved_at": document.approved_at,
        }
        if document.approved_version
        else None,
    }


def _vendor(db: Session, workspace_id: str, name: str | None) -> Vendor | None:
    if not name:
        return None
    normalized = re.sub(r"\s+", " ", name).strip().casefold()
    vendor = db.scalar(
        select(Vendor).where(
            Vendor.workspace_id == workspace_id, Vendor.normalized_name == normalized
        )
    )
    if not vendor:
        vendor = Vendor(workspace_id=workspace_id, name=name.strip(), normalized_name=normalized)
        db.add(vendor)
        db.flush()
    return vendor


def persist_extraction(
    db: Session,
    document: Document,
    extracted,
    pages: list[PageContent],
    source: str,
    field_pages: dict[str, int] | None = None,
    line_pages: dict[int, int] | None = None,
) -> None:
    if document.version:
        return
    fields = {}
    for key in FIELD_KEYS:
        value = getattr(extracted, key)
        source_pages = (
            [page for page in pages if page.number == field_pages[key]]
            if field_pages and key in field_pages
            else pages
        )
        fields[key] = locate_evidence(value, source_pages, source, key)
    lines = []
    used_rows: set[tuple[int, int, int]] = set()
    for index, line in enumerate(extracted.lines):
        item = line.model_dump()
        source_pages = (
            [page for page in pages if page.number == line_pages[index]]
            if line_pages and index in line_pages
            else pages
        )
        item["evidence"] = locate_line_evidence(item, source_pages, source, used_rows)
        lines.append(item)
    data = {"kind": extracted.kind, "fields": fields, "lines": lines, "normalized": False}
    version = ExtractionVersion(
        workspace_id=document.workspace_id,
        document_id=document.id,
        version=1,
        data=data,
        content_hash=content_hash(data),
        source=source,
    )
    db.add(version)
    document.version = 1
    document.kind = extracted.kind
    document.status = "processing"
    db.flush()
    for key, evidence in fields.items():
        db.add(
            ExtractedFieldEvidence(
                workspace_id=document.workspace_id,
                extraction_version_id=version.id,
                field_key=key,
                **evidence,
            )
        )
    for index, line in enumerate(lines):
        for key, evidence in line["evidence"].items():
            db.add(
                ExtractedFieldEvidence(
                    workspace_id=document.workspace_id,
                    extraction_version_id=version.id,
                    field_key=f"lines.{index}.{key}",
                    **evidence,
                )
            )
    db.commit()


def normalize_version(db: Session, document: Document) -> None:
    version = version_row(db, document)
    if version is None or version.data.get("normalized"):
        return
    data = copy.deepcopy(version.data)
    fields = data["fields"]
    scanned = any(page.source_type == "scanned" for page in document.pages)
    currency_raw = fields.get("currency", {}).get("raw")
    currency = (
        _ocr_currency(currency_raw) if scanned else normalize_configured("currency", currency_raw)
    )
    for key, evidence in fields.items():
        raw = evidence.get("raw")
        if scanned and key in {"number", "po_number"}:
            raw = _ocr_identifier(raw)
        elif scanned and key == "vendor" and _contaminated_vendor_name(raw):
            raw = None
        evidence["value"] = (
            currency if key == "currency" else normalize_configured(key, raw, currency)
        )
    for line in data["lines"]:
        for key in ("quantity", "unit_price", "amount"):
            line[key] = normalize_configured(f"line.{key}", line.get(key), currency)
            if line.get("evidence", {}).get(key):
                line["evidence"][key]["value"] = line[key]
    data["normalized"] = True
    version.data = data
    version.content_hash = content_hash(data)
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(version, "data")
    vendor = _vendor(db, document.workspace_id, fields.get("vendor", {}).get("value"))
    document.vendor_id = vendor.id if vendor else None
    document.number = fields.get("number", {}).get("value")
    document.po_number = fields.get("po_number", {}).get("value")
    document.date = fields.get("date", {}).get("value")
    document.currency = currency
    document.total = fields.get("total", {}).get("value")
    for evidence_row in db.scalars(
        select(ExtractedFieldEvidence).where(
            ExtractedFieldEvidence.extraction_version_id == version.id
        )
    ):
        if evidence_row.field_key.startswith("lines."):
            _, index, key = evidence_row.field_key.split(".")
            evidence_row.value = data["lines"][int(index)]["evidence"][key].get("value")
        else:
            evidence_row.value = fields[evidence_row.field_key].get("value")
    materialize_document(db, document, data)
    db.commit()


def materialize_document(db: Session, document: Document, data: dict) -> None:
    fields = data["fields"]
    if document.kind in {"invoice", "credit_note"}:
        invoice = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
        if not invoice:
            invoice = Invoice(workspace_id=document.workspace_id, document_id=document.id)
            db.add(invoice)
            db.flush()
        invoice.vendor_id = document.vendor_id
        invoice.invoice_number = document.number
        invoice.po_number = document.po_number
        invoice.currency = document.currency
        invoice.total = document.total
        db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
        for index, line in enumerate(data.get("lines", [])):
            db.add(
                InvoiceLine(
                    workspace_id=document.workspace_id,
                    invoice_id=invoice.id,
                    position=index,
                    sku=line.get("sku"),
                    description=line.get("description"),
                    quantity=line.get("quantity"),
                    unit=line.get("unit"),
                    unit_price=line.get("unit_price"),
                    amount=line.get("amount"),
                )
            )
    elif document.kind == "purchase_order":
        po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.document_id == document.id))
        if not po:
            po = PurchaseOrder(workspace_id=document.workspace_id, document_id=document.id)
            db.add(po)
            db.flush()
        po.vendor_id = document.vendor_id
        po.po_number = fields.get("po_number", {}).get("value") or document.number
        po.currency = document.currency
        db.execute(delete(POLine).where(POLine.po_id == po.id))
        for index, line in enumerate(data.get("lines", [])):
            db.add(
                POLine(
                    workspace_id=document.workspace_id,
                    po_id=po.id,
                    position=index,
                    sku=line.get("sku"),
                    description=line.get("description"),
                    quantity=line.get("quantity"),
                    unit_price=line.get("unit_price"),
                    amount=line.get("amount"),
                )
            )


def _ambiguous_vendor_findings(db: Session, document: Document, data: dict) -> list[dict]:
    if document.kind != "invoice":
        return []
    evidence = data.get("fields", {}).get("vendor", {})
    value = evidence.get("value")
    if not value or evidence.get("source") == "manual":
        return []
    normalized = re.sub(r"\s+", " ", value).strip().casefold()
    if len(normalized.split()) < 2:
        return []
    tokens = normalized.split()

    def ordered_name_tokens(candidate: str) -> bool:
        if candidate == normalized:
            return False
        remaining = iter(candidate.split())
        return all(token in remaining for token in tokens)

    vendors = db.scalars(select(Vendor).where(Vendor.workspace_id == document.workspace_id)).all()
    candidates = sorted(
        (
            vendor
            for vendor in vendors
            if ordered_name_tokens(vendor.normalized_name)
            and not _contaminated_vendor_name(vendor.name)
        ),
        key=lambda vendor: (vendor.normalized_name, vendor.id),
    )
    if len(candidates) < 2:
        return []
    return [
        {
            "code": "AMBIGUOUS_VENDOR",
            "severity": "warning",
            "message": f"Vendor name {value} could refer to several vendors; correct it to a full name",
            "details": {
                "candidate_vendors": [
                    {"id": vendor.id, "name": vendor.name} for vendor in candidates[:5]
                ]
            },
        }
    ]


def _numeric_suffix(value: str) -> str | None:
    match = re.search(r"(\d{3,})$", value)
    return match.group(1) if match else None


def _line_amount_verified(
    quantity: str | None,
    unit_price: str | None,
    line_amount: str | None,
    currency: str | None,
) -> bool:
    """A comparison is reliable only when the source row proves its own arithmetic."""
    parsed_quantity = amount(quantity)
    parsed_price = amount(unit_price)
    parsed_amount = amount(line_amount)
    return (
        parsed_quantity is not None
        and parsed_price is not None
        and parsed_amount is not None
        and parsed_quantity >= 0
        and quantize(parsed_quantity * parsed_price, currency) == quantize(parsed_amount, currency)
    )


def _po_findings(
    db: Session, document: Document, data: dict
) -> tuple[list[dict], list[tuple[PurchaseOrder, float, dict]]]:
    if document.kind != "invoice":
        return [], []
    findings: list[dict] = []
    candidates: list[tuple[PurchaseOrder, float, dict]] = []
    resolution = data.get("match_resolution")
    po_number = document.po_number
    if not po_number:
        if resolution and resolution.get("decision") == "rejected":
            return [], []
        return [
            {
                "code": "MISSING_PO",
                "severity": "warning",
                "message": "No purchase order reference was extracted",
                "details": {},
            }
        ], []
    all_pos = db.scalars(
        select(PurchaseOrder).where(
            PurchaseOrder.workspace_id == document.workspace_id,
            PurchaseOrder.po_number.is_not(None),
        )
    ).all()
    exact_matches = [
        po for po in all_pos if po.po_number and po.po_number.casefold() == po_number.casefold()
    ]
    if exact_matches:
        all_pos = exact_matches
    for po in all_pos:
        exact = po.po_number and po.po_number.casefold() == po_number.casefold()
        score = 1.0 if exact else SequenceMatcher(None, po.po_number or "", po_number).ratio()
        if not exact:
            if document.vendor_id and po.vendor_id != document.vendor_id:
                continue
            ref_suffix, candidate_suffix = (
                _numeric_suffix(po_number),
                _numeric_suffix(po.po_number or ""),
            )
            if ref_suffix and candidate_suffix and ref_suffix != candidate_suffix:
                continue
        if exact or score >= 0.9:
            candidates.append(
                (
                    po,
                    score,
                    {
                        "method": "identifier" if exact else "fuzzy_identifier",
                        "vendor_match": bool(
                            document.vendor_id and po.vendor_id == document.vendor_id
                        ),
                    },
                )
            )
    candidates.sort(key=lambda item: (item[1], item[2]["vendor_match"], item[0].id), reverse=True)
    candidates = candidates[:5]
    if resolution and resolution.get("decision") == "rejected":
        return [], candidates
    if not candidates:
        if resolution and resolution.get("decision") == "selected":
            return [
                {
                    "code": "PO_SELECTION_STALE",
                    "severity": "warning",
                    "message": "Selected purchase order is no longer a current proposal",
                    "details": {"po_id": resolution.get("po_id")},
                }
            ], []
        return [
            {
                "code": "PO_NOT_FOUND",
                "severity": "warning",
                "message": f"No purchase order matches reference {po_number}",
                "details": {"po_number": po_number},
            }
        ], []
    selected = None
    if resolution and resolution.get("decision") == "selected":
        selected = next(
            (candidate for candidate in candidates if candidate[0].id == resolution.get("po_id")),
            None,
        )
        if selected is None:
            findings.append(
                {
                    "code": "PO_SELECTION_STALE",
                    "severity": "warning",
                    "message": "Selected purchase order is no longer a current proposal",
                    "details": {"po_id": resolution.get("po_id")},
                }
            )
            return findings, candidates
    else:
        same_vendor_exact = [
            candidate
            for candidate in candidates
            if candidate[1] == 1 and candidate[2]["vendor_match"]
        ]
        if len(same_vendor_exact) == 1:
            selected = same_vendor_exact[0]
            selected[2]["automatic"] = True
    if selected is None and len(candidates) > 1:
        findings.append(
            {
                "code": "AMBIGUOUS_PO",
                "severity": "warning",
                "message": "Several purchase orders are plausible; choose one manually",
                "details": {"candidate_count": len(candidates)},
            }
        )
        return findings, candidates
    if selected is None:
        findings.append(
            {
                "code": "PO_SELECTION_REQUIRED",
                "severity": "warning",
                "message": "Confirm the proposed purchase order before approval",
                "details": {"po_id": candidates[0][0].id},
            }
        )
        return findings, candidates
    po = selected[0]
    if document.vendor_id and po.vendor_id and document.vendor_id != po.vendor_id:
        findings.append(
            {
                "code": "PO_VENDOR_MISMATCH",
                "severity": "error",
                "message": "Invoice vendor differs from the selected purchase order vendor",
                "details": {"po_id": po.id},
            }
        )
    if po.currency and document.currency and po.currency != document.currency:
        findings.append(
            {
                "code": "CROSS_CURRENCY",
                "severity": "error",
                "message": f"Invoice is {document.currency}; purchase order is {po.currency}. No exchange-rate source is configured",
                "details": {"invoice_currency": document.currency, "po_currency": po.currency},
            }
        )
    po_lines = db.scalars(select(POLine).where(POLine.po_id == po.id)).all()
    invoice_lines = data.get("lines", [])
    po_by_sku: dict[str, list[POLine]] = defaultdict(list)
    for line in po_lines:
        if line.sku:
            po_by_sku[line.sku.casefold()].append(line)
    invoice_by_sku: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, line in enumerate(invoice_lines):
        if line.get("sku"):
            invoice_by_sku[line["sku"].casefold()].append((index, line))
    line_matches = data.setdefault("line_matches", {})
    for sku, inv_group in invoice_by_sku.items():
        po_group = po_by_sku.get(sku)
        if not po_group:
            findings.append(
                {
                    "code": "SKU_NOT_ON_PO",
                    "severity": "warning",
                    "message": f"SKU {sku} is not on the purchase order",
                    "details": {"sku": sku},
                }
            )
            continue
        unverified_po_lines = [
            line
            for line in po_group
            if not _line_amount_verified(line.quantity, line.unit_price, line.amount, po.currency)
        ]
        if unverified_po_lines:
            findings.append(
                {
                    "code": "PO_LINE_SOURCE_UNVERIFIED",
                    "severity": "warning",
                    "message": f"SKU {sku}: correct the selected PO line quantity, price, or amount before comparing",
                    "details": {
                        "sku": sku,
                        "po_id": po.id,
                        "po_line_ids": [line.id for line in unverified_po_lines],
                    },
                }
            )
        invoice_quantities = [amount(line.get("quantity")) for _, line in inv_group]
        po_quantities = [amount(line.quantity) for line in po_group]
        if (
            not unverified_po_lines
            and all(quantity is not None and quantity >= 0 for quantity in invoice_quantities)
            and all(quantity is not None and quantity >= 0 for quantity in po_quantities)
            and sum(cast(Decimal, quantity) for quantity in invoice_quantities)
            > sum(cast(Decimal, quantity) for quantity in po_quantities)
        ):
            inv_qty = sum(cast(Decimal, quantity) for quantity in invoice_quantities)
            po_qty = sum(cast(Decimal, quantity) for quantity in po_quantities)
            findings.append(
                {
                    "code": "QUANTITY_OVER_PO",
                    "severity": "error",
                    "message": f"SKU {sku}: invoiced quantity {inv_qty} exceeds ordered {po_qty}",
                    "details": {"sku": sku, "invoiced": str(inv_qty), "ordered": str(po_qty)},
                }
            )
        unresolved = []
        mapped_quantities: dict[str, Decimal] = defaultdict(Decimal)
        for index, inv_line in inv_group:
            # A single PO row gives a deterministic mapping for every invoice
            # row. Persist it, including partial shipments with repeated SKUs.
            if len(po_group) == 1:
                line_matches[str(index)] = po_group[0].id
            selected_line = next(
                (line for line in po_group if line.id == line_matches.get(str(index))),
                None,
            )
            if selected_line is None:
                unresolved.append(index)
                continue
            mapped_quantities[selected_line.id] += amount(inv_line.get("quantity")) or Decimal(0)
            if (
                document.currency == po.currency
                and _line_amount_verified(
                    inv_line.get("quantity"),
                    inv_line.get("unit_price"),
                    inv_line.get("amount"),
                    document.currency,
                )
                and _line_amount_verified(
                    selected_line.quantity,
                    selected_line.unit_price,
                    selected_line.amount,
                    po.currency,
                )
            ):
                expected = amount(selected_line.unit_price)
                actual = amount(inv_line.get("unit_price"))
                if (
                    expected is not None
                    and actual is not None
                    and quantize(actual, document.currency) != quantize(expected, document.currency)
                ):
                    findings.append(
                        {
                            "code": "UNIT_PRICE_MISMATCH",
                            "severity": "error",
                            "message": f"SKU {sku}: invoice unit price {actual}, selected PO line price {expected}",
                            "details": {
                                "sku": sku,
                                "invoice_line_index": index,
                                "po_line_id": selected_line.id,
                                "invoice_price": str(actual),
                                "po_price": str(expected),
                            },
                        }
                    )
        quantity_check_lines = po_group if len(po_group) > 1 else []
        for selected_line in quantity_check_lines:
            if selected_line in unverified_po_lines:
                continue
            mapped_qty = mapped_quantities.get(selected_line.id, Decimal(0))
            ordered_qty = amount(selected_line.quantity)
            if ordered_qty is None:
                continue
            if mapped_qty > ordered_qty:
                findings.append(
                    {
                        "code": "QUANTITY_OVER_PO_LINE",
                        "severity": "error",
                        "message": f"SKU {sku}: mapped quantity {mapped_qty} exceeds PO line quantity {ordered_qty}",
                        "details": {
                            "sku": sku,
                            "po_line_id": selected_line.id,
                            "invoiced": str(mapped_qty),
                            "ordered": str(ordered_qty),
                        },
                    }
                )
        if unresolved:
            findings.append(
                {
                    "code": "AMBIGUOUS_LINE_MATCH",
                    "severity": "warning",
                    "message": f"SKU {sku} has multiple PO lines; select a PO line for each invoice line",
                    "details": {
                        "sku": sku,
                        "invoice_line_indices": unresolved,
                        "candidates": [
                            {
                                "po_line_id": line.id,
                                "description": line.description,
                                "quantity": line.quantity,
                                "unit_price": line.unit_price,
                                "amount": line.amount,
                            }
                            for line in po_group
                        ],
                    },
                }
            )
    return findings, candidates


def refresh_findings(db: Session, document: Document, *, commit: bool = True) -> None:
    version = version_row(db, document)
    if not version:
        return
    data = copy.deepcopy(version.data)
    claimed = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == version.version,
        )
        .values(updated_at=Document.updated_at)
    )
    if cast(Any, claimed).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Document version changed during validation")
    db.refresh(document)
    previous = db.scalars(
        select(Finding).where(
            Finding.document_id == document.id, Finding.extraction_version == document.version
        )
    ).all()
    old_by_signature = {
        (row.code, json.dumps(row.details, sort_keys=True)): row for row in previous
    }
    db.execute(
        delete(MatchProposal).where(
            MatchProposal.document_id == document.id,
            MatchProposal.extraction_version == document.version,
        )
    )
    findings = validate_arithmetic(data)
    findings.extend(_ambiguous_vendor_findings(db, document, data))
    if document.kind == "invoice" and document.vendor_id and document.number:
        duplicates = db.scalars(
            select(Invoice).where(
                Invoice.workspace_id == document.workspace_id,
                Invoice.vendor_id == document.vendor_id,
                Invoice.invoice_number == document.number,
                Invoice.document_id != document.id,
            )
        ).all()
        if duplicates:
            findings.append(
                {
                    "code": "DUPLICATE_INVOICE",
                    "severity": "error",
                    "message": "This vendor and invoice number already appear in another document",
                    "details": {"document_ids": [row.document_id for row in duplicates]},
                }
            )
    po_findings, proposals = _po_findings(db, document, data)
    findings.extend(po_findings)
    if data != version.data:
        # Deterministic row mappings are part of the reviewed extraction.
        # A newly arrived PO can add them to an existing version, so the
        # content hash and any approval must be updated together.
        version.data = data
        version.content_hash = content_hash(data)
        document.approved_version = None
        document.approved_hash = None
        document.approved_by = None
        document.approved_at = None
    resolution = data.get("match_resolution")
    for po, score, details in proposals:
        if resolution and resolution.get("decision") == "selected":
            status = "selected" if po.id == resolution.get("po_id") else "rejected"
        elif resolution and resolution.get("decision") == "rejected":
            status = "rejected"
        else:
            status = "matched" if details.get("automatic") else "proposed"
        db.add(
            MatchProposal(
                workspace_id=document.workspace_id,
                document_id=document.id,
                extraction_version=document.version,
                po_id=po.id,
                score=score,
                status=status,
                details=details,
            )
        )
    new_signatures = {
        (finding["code"], json.dumps(finding["details"], sort_keys=True)) for finding in findings
    }
    changed = new_signatures != set(old_by_signature)
    for signature, prior in old_by_signature.items():
        if signature in new_signatures:
            continue
        if prior.status == "open":
            db.delete(prior)
        else:
            prior.status = "superseded"
    for finding in findings:
        signature = (finding["code"], json.dumps(finding["details"], sort_keys=True))
        prior = old_by_signature.get(signature)
        if prior:
            prior.message = finding["message"]
            prior.severity = finding["severity"]
            continue
        db.add(
            Finding(
                workspace_id=document.workspace_id,
                document_id=document.id,
                extraction_version=document.version,
                **finding,
            )
        )
    if changed and document.approved_version is not None:
        document.approved_version = None
        document.approved_hash = None
        document.approved_by = None
        document.approved_at = None
    if document.approved_version is None:
        document.status = "needs_review"
    if commit:
        db.commit()
    else:
        db.flush()


def _copy_evidence(db: Session, document: Document, version: ExtractionVersion, data: dict) -> None:
    for key, evidence in data["fields"].items():
        db.add(
            ExtractedFieldEvidence(
                workspace_id=document.workspace_id,
                extraction_version_id=version.id,
                field_key=key,
                **evidence,
            )
        )
    for index, line in enumerate(data["lines"]):
        for key, evidence in line.get("evidence", {}).items():
            db.add(
                ExtractedFieldEvidence(
                    workspace_id=document.workspace_id,
                    extraction_version_id=version.id,
                    field_key=f"lines.{index}.{key}",
                    **evidence,
                )
            )


def apply_correction(
    db: Session, document: Document, user: User, field: str, value: str | None, reason: str
) -> None:
    expected_version = document.version
    claim = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == expected_version,
        )
        .values(updated_at=Document.updated_at)
    )
    claimed = cast(Any, claim).rowcount == 1
    if not claimed:
        db.rollback()
    db.refresh(document)
    old = version_row(db, document)
    if old is None:
        raise HTTPException(409, "Document has not been extracted")
    old_po_number = document.po_number
    data = copy.deepcopy(old.data)
    data.pop("match_resolution", None)
    data.pop("line_matches", None)
    before = None
    if field.startswith("lines."):
        parts = field.split(".")
        if (
            len(parts) != 3
            or not parts[1].isdigit()
            or int(parts[1]) >= len(data.get("lines", []))
            or parts[2] not in {"sku", "description", "quantity", "unit", "unit_price", "amount"}
        ):
            raise HTTPException(422, "Invalid line field")
        line = data["lines"][int(parts[1])]
        before = line.get(parts[2])
        normalized_value = normalize_configured(
            f"line.{parts[2]}", value, data["fields"].get("currency", {}).get("value")
        )
        line[parts[2]] = normalized_value
        if line.get("evidence", {}).get(parts[2]):
            line["evidence"][parts[2]]["value"] = normalized_value
            line["evidence"][parts[2]]["source"] = "manual"
    elif field in FIELD_KEYS:
        evidence = data["fields"][field]
        before = evidence.get("value")
        normalized_value = normalize_configured(
            field, value, data["fields"].get("currency", {}).get("value")
        )
        # Preserve the source reading and its location; the corrected value is
        # separately recorded in the new version and audit entry.
        evidence.update({"value": normalized_value, "source": "manual"})
    else:
        raise HTTPException(422, "Unknown correction field")
    needs_normalized_value = field in {
        "date",
        "due_date",
        "currency",
        "subtotal",
        "tax",
        "freight",
        "discounts",
        "total",
    } or field.endswith((".quantity", ".unit_price", ".amount"))
    if value is not None and needs_normalized_value and normalized_value is None:
        raise HTTPException(422, "Value cannot be normalized")
    if before == normalized_value:
        if claimed:
            db.commit()
        return
    if not claimed:
        raise HTTPException(409, "Document version changed; reload before correcting")
    dependent_ids: set[str] = set()
    if document.kind == "purchase_order":
        references = {
            reference
            for reference in (old_po_number, data["fields"]["po_number"].get("value"))
            if reference
        }
        if references:
            dependent_ids.update(
                db.scalars(
                    select(Document.id).where(
                        Document.workspace_id == document.workspace_id,
                        Document.kind.in_(["invoice", "credit_note"]),
                        Document.po_number.in_(references),
                    )
                ).all()
            )
        current_po = db.scalar(
            select(PurchaseOrder).where(PurchaseOrder.document_id == document.id)
        )
        if current_po:
            dependent_ids.update(
                db.scalars(
                    select(MatchProposal.document_id).where(
                        MatchProposal.workspace_id == document.workspace_id,
                        MatchProposal.po_id == current_po.id,
                    )
                ).all()
            )
        # Approval claims an invoice before its PO. Claim dependent invoices
        # in that same order before rewriting PO lines to avoid a deadlock.
        for dependent_id in sorted(dependent_ids):
            db.execute(
                update(Document)
                .where(Document.id == dependent_id, Document.workspace_id == document.workspace_id)
                .values(updated_at=Document.updated_at)
            )
    new_number = document.version + 1
    new_version = ExtractionVersion(
        workspace_id=document.workspace_id,
        document_id=document.id,
        version=new_number,
        data=data,
        content_hash=content_hash(data),
        source="correction",
        created_by=user.id,
        reason=reason,
    )
    db.add(new_version)
    document.version = new_number
    document.approved_version = None
    document.approved_hash = None
    document.approved_by = None
    document.approved_at = None
    document.status = "validating"
    db.flush()
    _copy_evidence(db, document, new_version, data)
    document.kind = data["kind"]
    document.number = data["fields"].get("number", {}).get("value")
    document.po_number = data["fields"].get("po_number", {}).get("value")
    document.date = data["fields"].get("date", {}).get("value")
    document.currency = data["fields"].get("currency", {}).get("value")
    document.total = data["fields"].get("total", {}).get("value")
    vendor = _vendor(db, document.workspace_id, data["fields"].get("vendor", {}).get("value"))
    document.vendor_id = vendor.id if vendor else None
    materialize_document(db, document, data)
    db.add(
        ReviewDecision(
            workspace_id=document.workspace_id,
            document_id=document.id,
            extraction_version=new_number,
            user_id=user.id,
            action="correction",
            note=reason,
            before={field: before},
            after={field: value},
        )
    )
    if document.kind == "purchase_order":
        # The corrected PO and every dependent approval change atomically.
        db.flush()
        refresh_findings(db, document, commit=False)
        if dependent_ids:
            dependents = db.scalars(
                select(Document).where(
                    Document.workspace_id == document.workspace_id,
                    Document.id.in_(dependent_ids),
                )
            ).all()
            for dependent in dependents:
                if dependent.approved_version is not None:
                    db.add(
                        ReviewDecision(
                            workspace_id=dependent.workspace_id,
                            document_id=dependent.id,
                            extraction_version=dependent.version,
                            user_id=user.id,
                            action="po_correction_invalidation",
                            note=reason,
                            before={"approved_hash": dependent.approved_hash},
                            after={"po_document_id": document.id, "po_version": document.version},
                        )
                    )
                    dependent.approved_version = None
                    dependent.approved_hash = None
                    dependent.approved_by = None
                    dependent.approved_at = None
                    dependent.status = "needs_review"
                refresh_findings(db, dependent, commit=False)
        db.commit()
    else:
        db.commit()
        refresh_findings(db, document)


def _save_review_version(
    db: Session,
    document: Document,
    user: User,
    data: dict,
    action: str,
    before: dict | None,
    after: dict,
    note: str | None,
) -> None:
    previous_number = document.version
    new_number = previous_number + 1
    changed = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == previous_number,
        )
        .values(
            version=new_number,
            approved_version=None,
            approved_hash=None,
            approved_by=None,
            approved_at=None,
            status="validating",
        )
    )
    if cast(Any, changed).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Document version changed; reload before reviewing")
    new_version = ExtractionVersion(
        workspace_id=document.workspace_id,
        document_id=document.id,
        version=new_number,
        data=data,
        content_hash=content_hash(data),
        source="review",
        created_by=user.id,
        reason=action,
    )
    db.add(new_version)
    db.flush()
    _copy_evidence(db, document, new_version, data)
    db.add(
        ReviewDecision(
            workspace_id=document.workspace_id,
            document_id=document.id,
            extraction_version=new_number,
            user_id=user.id,
            action=action,
            note=note,
            before=before,
            after=after,
        )
    )
    db.commit()
    db.refresh(document)
    refresh_findings(db, document)


def decide_match(
    db: Session,
    document: Document,
    user: User,
    version: int,
    decision: str,
    po_id: str | None,
    note: str | None,
) -> None:
    if document.kind != "invoice":
        raise HTTPException(409, "Only invoices can resolve purchase order matches")
    if document.version != version:
        raise HTTPException(409, "Document version changed; reload before reviewing")
    if (decision == "selected") != bool(po_id):
        raise HTTPException(422, "Select a proposed PO, or reject all with po_id null")
    prior = version_row(db, document)
    if prior is None:
        raise HTTPException(409, "Document has not been extracted")
    before = prior.data.get("match_resolution")
    if before and before.get("decision") == decision and before.get("po_id") == po_id:
        return
    if po_id and not db.scalar(
        select(MatchProposal).where(
            MatchProposal.workspace_id == document.workspace_id,
            MatchProposal.document_id == document.id,
            MatchProposal.extraction_version == version,
            MatchProposal.po_id == po_id,
        )
    ):
        raise HTTPException(422, "PO is not a current proposal for this invoice")
    data = copy.deepcopy(prior.data)
    after = {
        "version": version + 1,
        "decision": decision,
        "po_id": po_id,
        "note": note,
    }
    data["match_resolution"] = after
    data.pop("line_matches", None)
    _save_review_version(db, document, user, data, "po_match_decision", before, after, note)


def decide_line_match(
    db: Session,
    document: Document,
    user: User,
    version: int,
    invoice_line_index: int,
    po_line_id: str,
    note: str | None,
) -> None:
    if document.kind != "invoice" or document.version != version:
        raise HTTPException(409, "Invoice version changed; reload before reviewing")
    prior = version_row(db, document)
    if prior is None or invoice_line_index >= len(prior.data.get("lines", [])):
        raise HTTPException(422, "Invoice line does not exist")
    chosen_match = db.scalar(
        select(MatchProposal).where(
            MatchProposal.workspace_id == document.workspace_id,
            MatchProposal.document_id == document.id,
            MatchProposal.extraction_version == version,
            MatchProposal.status.in_(["selected", "matched"]),
        )
    )
    if chosen_match is None:
        raise HTTPException(409, "Select a purchase order before mapping lines")
    po_line = db.scalar(
        select(POLine).where(
            POLine.id == po_line_id,
            POLine.workspace_id == document.workspace_id,
            POLine.po_id == chosen_match.po_id,
        )
    )
    invoice_line = prior.data["lines"][invoice_line_index]
    if (
        po_line is None
        or not po_line.sku
        or not invoice_line.get("sku")
        or po_line.sku.casefold() != invoice_line["sku"].casefold()
    ):
        raise HTTPException(422, "PO line must belong to the matched PO and have the same SKU")
    key = str(invoice_line_index)
    before_line_id = prior.data.get("line_matches", {}).get(key)
    if before_line_id == po_line_id:
        return
    data = copy.deepcopy(prior.data)
    data.setdefault("line_matches", {})[key] = po_line_id
    if data.get("match_resolution"):
        data["match_resolution"]["version"] = version + 1
    _save_review_version(
        db,
        document,
        user,
        data,
        "line_match_decision",
        {"invoice_line_index": invoice_line_index, "po_line_id": before_line_id},
        {"invoice_line_index": invoice_line_index, "po_line_id": po_line_id},
        note,
    )


def decide_finding(
    db: Session, document: Document, finding_id: str, user: User, decision: str, note: str | None
) -> None:
    if user.workspace_id != document.workspace_id or user.role not in {"admin", "operator"}:
        raise HTTPException(403, "Review access required")
    if decision not in {"accepted", "rejected"}:
        raise HTTPException(422, "Choose accepted or rejected")
    expected_version = document.version
    # Claim the document row before reading the finding. This serializes review
    # changes with approval and export on PostgreSQL and SQLite.
    claim = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == expected_version,
        )
        .values(updated_at=Document.updated_at)
    )
    if cast(Any, claim).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Document version changed; reload before reviewing")
    db.refresh(document)
    finding = db.scalar(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.workspace_id == document.workspace_id,
            Finding.document_id == document.id,
            Finding.extraction_version == document.version,
        )
    )
    if not finding:
        db.rollback()
        raise HTTPException(404, "Finding not found for current version")
    if finding.status == decision:
        db.commit()
        return
    prior_status = finding.status
    finding.status = decision
    document.approved_version = None
    document.approved_hash = None
    document.approved_by = None
    document.approved_at = None
    document.status = "needs_review"
    db.add(
        ReviewDecision(
            workspace_id=document.workspace_id,
            document_id=document.id,
            extraction_version=document.version,
            finding_id=finding.id,
            user_id=user.id,
            action="finding_decision",
            note=note,
            before={"status": prior_status},
            after={"status": decision},
        )
    )
    db.commit()


REVIEW_BLOCKER_CODES = {
    "AMBIGUOUS_VENDOR",
    "AMBIGUOUS_PO",
    "AMBIGUOUS_LINE_MATCH",
    "PO_SELECTION_REQUIRED",
    "PO_SELECTION_STALE",
    "PO_LINE_SOURCE_UNVERIFIED",
}


def approval_blocker_count(db: Session, document: Document) -> int:
    return (
        db.scalar(
            select(func.count(Finding.id)).where(
                Finding.document_id == document.id,
                Finding.extraction_version == document.version,
                (Finding.code.in_(REVIEW_BLOCKER_CODES))
                | ((Finding.severity == "error") & (Finding.status == "open")),
            )
        )
        or 0
    )


def approval_ready(
    db: Session, document: Document, extraction: ExtractionVersion | None = None
) -> bool:
    current = extraction or version_row(db, document)
    if (
        current is None
        or current.version != document.version
        or document.kind not in {"invoice", "credit_note", "purchase_order"}
        or current.data.get("kind") != document.kind
        or not current.data.get("normalized")
        or document.status not in {"needs_review", "approved"}
    ):
        return False
    latest_job = db.scalar(
        select(Job)
        .where(Job.workspace_id == document.workspace_id, Job.document_id == document.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
    )
    return latest_job is not None and latest_job.status == "complete"


def _po_line_claims(data: dict, po_lines: Sequence[POLine]) -> dict[str, Decimal]:
    lines_by_id = {line.id: line for line in po_lines}
    lines_by_sku: dict[str, list[POLine]] = defaultdict(list)
    for line in po_lines:
        if line.sku:
            lines_by_sku[line.sku.casefold()].append(line)
    claims: dict[str, Decimal] = defaultdict(Decimal)
    mappings = data.get("line_matches", {})
    for index, line in enumerate(data.get("lines", [])):
        line_id = mappings.get(str(index))
        if not line_id:
            sku = line.get("sku")
            candidates = lines_by_sku.get(sku.casefold(), []) if sku else []
            if len(candidates) == 1:
                line_id = candidates[0].id
            elif candidates:
                raise HTTPException(409, "Map every ambiguous invoice line before approval")
            else:
                continue
        if line_id not in lines_by_id:
            raise HTTPException(409, "PO line mapping is stale; revalidate the invoice")
        quantity = amount(line.get("quantity"))
        if (
            quantity is None
            or quantity < 0
            or amount(line.get("unit_price")) is None
            or amount(line.get("amount")) is None
        ):
            raise HTTPException(
                409, "A mapped invoice line has incomplete quantity, price, or amount"
            )
        claims[line_id] += quantity
    return claims


def _check_cumulative_po_claims(
    db: Session, document: Document, extraction: ExtractionVersion
) -> None:
    if document.kind != "invoice":
        return
    selected = db.scalars(
        select(MatchProposal).where(
            MatchProposal.workspace_id == document.workspace_id,
            MatchProposal.document_id == document.id,
            MatchProposal.extraction_version == document.version,
            MatchProposal.status.in_(["selected", "matched"]),
        )
    ).all()
    if not selected:
        return
    if len(selected) != 1:
        raise HTTPException(409, "Select one purchase order before approval")
    po_id = selected[0].po_id
    po_currency = db.scalar(select(PurchaseOrder.currency).where(PurchaseOrder.id == po_id))
    # Claim the PO row after the document row. Concurrent approvals for
    # different invoices against this PO then serialize before counting.
    claimed_po = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == po_id, PurchaseOrder.workspace_id == document.workspace_id)
        .values(po_number=PurchaseOrder.po_number)
    )
    if cast(Any, claimed_po).rowcount != 1:
        raise HTTPException(409, "Matched purchase order is no longer available")
    po_lines = db.scalars(
        select(POLine).where(POLine.po_id == po_id, POLine.workspace_id == document.workspace_id)
    ).all()
    quantities = _po_line_claims(extraction.data, po_lines)
    prior_matches = db.scalars(
        select(MatchProposal).where(
            MatchProposal.workspace_id == document.workspace_id,
            MatchProposal.po_id == po_id,
            MatchProposal.status.in_(["selected", "matched"]),
            MatchProposal.document_id != document.id,
        )
    ).all()
    counted: set[str] = set()
    for match in prior_matches:
        if match.document_id in counted:
            continue
        prior = db.scalar(
            select(Document).where(
                Document.id == match.document_id,
                Document.workspace_id == document.workspace_id,
                Document.kind == "invoice",
                Document.version == match.extraction_version,
                Document.approved_version == match.extraction_version,
            )
        )
        if not prior:
            continue
        prior_extraction = version_row(db, prior)
        if prior_extraction is None or prior_extraction.content_hash != prior.approved_hash:
            raise HTTPException(409, "A prior approved invoice needs revalidation")
        for line_id, quantity in _po_line_claims(prior_extraction.data, po_lines).items():
            quantities[line_id] += quantity
        counted.add(prior.id)
    for po_line in po_lines:
        ordered = amount(po_line.quantity)
        if ordered is None or ordered < 0:
            raise HTTPException(409, "Matched PO has an invalid ordered quantity")
        claimed = quantities.get(po_line.id, Decimal(0))
        if claimed and not _line_amount_verified(
            po_line.quantity, po_line.unit_price, po_line.amount, po_currency
        ):
            raise HTTPException(
                409,
                f"PO line {po_line.sku or po_line.id} has incomplete or inconsistent quantity, price, or amount; correct the PO",
            )
        if claimed > ordered:
            raise HTTPException(
                409,
                f"PO line {po_line.sku or po_line.id} has {claimed} invoiced across approved invoices; ordered quantity is {ordered}",
            )


def approve_document(db: Session, document: Document, version: int, user: User) -> None:
    if user.workspace_id != document.workspace_id or user.role not in {"admin", "operator"}:
        raise HTTPException(403, "Approval access required")
    claim = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == version,
        )
        .values(updated_at=Document.updated_at)
    )
    if cast(Any, claim).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Document version changed; review latest extraction")
    db.refresh(document)
    extraction = version_row(db, document)
    if not extraction:
        db.rollback()
        raise HTTPException(409, "Document has no extraction")
    if not approval_ready(db, document, extraction):
        db.rollback()
        raise HTTPException(409, "Document validation has not completed for this version")
    if approval_blocker_count(db, document):
        db.rollback()
        raise HTTPException(409, "Resolve required matches and open errors before approval")
    if document.approved_version == version and document.approved_hash == extraction.content_hash:
        db.commit()
        return
    _check_cumulative_po_claims(db, document, extraction)
    updated = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == version,
            Document.approved_version.is_(None),
        )
        .values(
            approved_version=version,
            approved_hash=extraction.content_hash,
            approved_by=user.id,
            approved_at=utcnow(),
            status="approved",
        )
    )
    if cast(Any, updated).rowcount != 1:
        db.rollback()
        current = db.scalar(
            select(Document).where(
                Document.id == document.id, Document.workspace_id == document.workspace_id
            )
        )
        if (
            current
            and current.approved_version == version
            and current.approved_hash == extraction.content_hash
        ):
            return
        raise HTTPException(409, "Document changed while approving")
    key = f"approve:{document.id}:{version}:{extraction.content_hash}"
    if not db.scalar(
        select(ActionLedger).where(
            ActionLedger.workspace_id == document.workspace_id, ActionLedger.action_key == key
        )
    ):
        db.add(
            ActionLedger(
                workspace_id=document.workspace_id,
                action_key=key,
                kind="approve",
                document_id=document.id,
                result_id=document.id,
            )
        )
    db.add(
        ReviewDecision(
            workspace_id=document.workspace_id,
            document_id=document.id,
            extraction_version=version,
            user_id=user.id,
            action="approve",
            after={"content_hash": extraction.content_hash},
        )
    )
    db.commit()


def _safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", text):
        return text
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def export_content(document: Document, data: dict, fmt: str) -> bytes:
    fields = data["fields"]
    record = {
        "schema_version": "1.0",
        "document_id": document.id,
        "document_version": document.version,
        "kind": document.kind,
        **{key: fields.get(key, {}).get("value") for key in FIELD_KEYS},
        "lines": data.get("lines", []),
    }
    if fmt == "json":
        return json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    columns = [
        "schema_version",
        "document_id",
        "document_version",
        "kind",
        *FIELD_KEYS,
        "line_sku",
        "line_description",
        "line_quantity",
        "line_unit",
        "line_unit_price",
        "line_amount",
    ]
    rows = []
    for line in record["lines"] or [{}]:
        rows.append(
            [record.get(key) for key in columns[:-6]]
            + [
                line.get(key)
                for key in ("sku", "description", "quantity", "unit", "unit_price", "amount")
            ]
        )
    if fmt == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(columns)
        writer.writerows([[_safe_cell(value) for value in row] for row in rows])
        return ("\ufeff" + buffer.getvalue()).encode("utf-8")
    if fmt == "xlsx":
        book = Workbook()
        sheet = book.active
        sheet.title = "Approved invoice"
        sheet.append(columns)
        for row in rows:
            sheet.append([_safe_cell(value) for value in row])
        sheet.freeze_panes = "A2"
        for column in sheet.columns:
            max_length = max(len(str(cell.value or "")) for cell in column)
            sheet.column_dimensions[column[0].column_letter].width = min(
                45, max(12, max_length + 2)
            )
        buffer = io.BytesIO()
        book.save(buffer)
        return buffer.getvalue()
    raise HTTPException(422, "Choose csv, xlsx, or json")


def get_export(db: Session, document: Document, fmt: str) -> tuple[bytes, str]:
    if fmt not in {"csv", "xlsx", "json"}:
        raise HTTPException(422, "Choose csv, xlsx, or json")
    # Conditional write claims the current approval under a database write lock.
    # It serializes a concurrent correction with export on SQLite and PostgreSQL.
    expected_version, expected_hash = document.version, document.approved_hash
    claim = db.execute(
        update(Document)
        .where(
            Document.id == document.id,
            Document.workspace_id == document.workspace_id,
            Document.version == expected_version,
            Document.approved_version == expected_version,
            Document.approved_hash == expected_hash,
        )
        .values(updated_at=Document.updated_at)
    )
    if cast(Any, claim).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Approval changed while exporting")
    db.refresh(document)
    version = version_row(db, document)
    if (
        not version
        or not approval_ready(db, document, version)
        or document.approved_version != document.version
        or document.approved_hash != version.content_hash
    ):
        raise HTTPException(409, "Approve the current document version before export")
    existing = db.scalar(
        select(ExportJob).where(
            ExportJob.workspace_id == document.workspace_id,
            ExportJob.document_id == document.id,
            ExportJob.version == document.version,
            ExportJob.format == fmt,
        )
    )
    if existing:
        return storage_path(
            document.workspace_id, existing.storage_key
        ).read_bytes(), f"{document.id}.{fmt}"
    content = export_content(document, version.data, fmt)
    key = f"export-{document.id}-v{document.version}.{fmt}"
    save_export(document.workspace_id, key, content)
    export = ExportJob(
        workspace_id=document.workspace_id,
        document_id=document.id,
        version=document.version,
        format=fmt,
        storage_key=key,
        sha256=digest(content),
    )
    db.add(export)
    db.flush()
    db.add(
        ActionLedger(
            workspace_id=document.workspace_id,
            action_key=f"export:{document.id}:{document.version}:{fmt}",
            kind="export",
            document_id=document.id,
            result_id=export.id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ExportJob).where(
                ExportJob.workspace_id == document.workspace_id,
                ExportJob.document_id == document.id,
                ExportJob.version == document.version,
                ExportJob.format == fmt,
            )
        )
        if not existing:
            raise
        content = storage_path(document.workspace_id, existing.storage_key).read_bytes()
    return content, f"{document.id}.{fmt}"
