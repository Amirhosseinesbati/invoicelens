from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserView(BaseModel):
    id: str
    email: str
    role: str
    workspace_id: str
    workspace_name: str


class LoginResponse(BaseModel):
    user: UserView


class OverviewView(BaseModel):
    total_documents: int
    needs_review: int
    approved: int
    processing: int
    findings_open: int
    vendors: int
    export_count: int


class DocumentSummary(BaseModel):
    id: str
    filename: str
    kind: str
    status: str
    vendor: str | None
    number: str | None
    date: str | None
    currency: str | None
    total: str | None
    version: int
    page_count: int
    findings_count: int
    created_at: datetime


class PageView(BaseModel):
    page_number: int
    text: str
    source_type: str
    width: float
    height: float


class FieldEvidence(BaseModel):
    raw: str | None
    value: str | None
    page_number: int | None
    span_start: int | None
    span_end: int | None
    bbox: list[float] | None
    source: str


class LineView(BaseModel):
    id: str
    sku: str | None
    description: str | None
    quantity: str | None
    unit: str | None
    unit_price: str | None
    amount: str | None
    evidence: dict[str, FieldEvidence] = Field(default_factory=dict)


class FindingView(BaseModel):
    id: str
    code: str
    severity: str
    message: str
    status: str
    details: dict[str, Any]


class MatchView(BaseModel):
    po_id: str
    document_id: str | None
    po_number: str | None
    score: float
    status: str
    details: dict[str, Any]


class HistoryView(BaseModel):
    id: str
    action: str
    note: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    version: int
    created_at: datetime


class ApprovalView(BaseModel):
    version: int
    hash: str
    approved_by: str
    approved_at: datetime


class MatchResolutionView(BaseModel):
    version: int
    decision: Literal["selected", "rejected"]
    po_id: str | None
    note: str | None = None


class POLineCandidateView(BaseModel):
    po_line_id: str
    description: str | None
    quantity: str | None
    unit_price: str | None
    amount: str | None


class LineMatchCandidateView(BaseModel):
    invoice_line_index: int
    sku: str
    candidates: list[POLineCandidateView]


class DocumentDetail(DocumentSummary):
    pages: list[PageView]
    fields: dict[str, FieldEvidence]
    lines: list[LineView]
    findings: list[FindingView]
    matches: list[MatchView]
    match_resolution: MatchResolutionView | None
    line_matches: dict[str, str]
    line_match_candidates: list[LineMatchCandidateView]
    history: list[HistoryView]
    approval: ApprovalView | None


class ExtractionVersionView(BaseModel):
    version: int
    source: str
    reason: str | None
    created_at: datetime
    fields: dict[str, FieldEvidence]
    lines: list[LineView]
    content_hash: str


class JobView(BaseModel):
    id: str
    document_id: str
    status: str
    progress: int
    current_page: int
    total_pages: int
    error: str | None
    created_at: datetime
    updated_at: datetime


class UploadItem(BaseModel):
    document_id: str | None
    job_id: str | None
    status: str
    deduplicated: bool
    error: str | None
    filename: str | None = None


class UploadResponse(BaseModel):
    items: list[UploadItem]


class VendorView(BaseModel):
    id: str
    name: str
    invoice_count: int


class SettingsView(BaseModel):
    mode: str
    model_configured: bool
    ocr_available: bool
    workspace_name: str
    export_formats: list[str]


class CorrectionRequest(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)


class DecisionRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class ApprovalRequest(BaseModel):
    version: int


class MatchDecisionRequest(BaseModel):
    version: int
    decision: Literal["selected", "rejected"]
    po_id: str | None = None
    note: str | None = Field(default=None, max_length=2000)


class LineMatchDecisionRequest(BaseModel):
    version: int
    invoice_line_index: int = Field(ge=0)
    po_line_id: str
    note: str | None = Field(default=None, max_length=2000)


class ExtractedLine(BaseModel):
    sku: str | None = None
    description: str | None = None
    quantity: str | None = None
    unit: str | None = None
    unit_price: str | None = None
    amount: str | None = None


class DocumentExtraction(BaseModel):
    kind: Literal["invoice", "credit_note", "purchase_order", "unknown"] = "unknown"
    vendor: str | None = None
    number: str | None = None
    po_number: str | None = None
    date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    tax: str | None = None
    freight: str | None = None
    discounts: str | None = None
    total: str | None = None
    lines: list[ExtractedLine] = Field(default_factory=list)
