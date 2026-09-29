export type Role = 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  email: string
  role: Role
  workspace_id: string
  workspace_name: string
}

export interface LoginResponse {
  user: User
}

export interface Overview {
  total_documents: number
  needs_review: number
  approved: number
  processing: number
  findings_open: number
  vendors: number
  export_count: number
}

export type DocumentKind = 'invoice' | 'purchase_order' | 'credit_note' | 'unknown' | string
export type DocumentStatus = 'uploaded' | 'queued' | 'processing' | 'needs_review' | 'approved' | 'failed' | 'cancelled' | string

export interface DocumentSummary {
  id: string
  filename: string
  kind: DocumentKind
  status: DocumentStatus
  vendor: string | null
  number: string | null
  date: string | null
  currency: string | null
  total: string | null
  version: number
  page_count: number
  findings_count: number
  created_at: string
}

export interface Page {
  page_number: number
  text: string
  source_type: string
  width: number
  height: number
}

export interface FieldEvidence {
  raw: string | null
  value: string | null
  page_number: number | null
  span_start: number | null
  span_end: number | null
  bbox: [number, number, number, number] | null
  source: string
}

export interface InvoiceLine {
  id: string
  sku: string | null
  description: string | null
  quantity: string | null
  unit: string | null
  unit_price: string | null
  amount: string | null
  evidence: Record<string, FieldEvidence>
}

export interface Finding {
  id: string
  code: string
  severity: string
  message: string
  status: string
  details: Record<string, unknown>
}

export interface MatchProposal {
  po_id: string
  po_number: string | null
  document_id: string | null
  score: number
  status: string
  details: Record<string, unknown>
}

export interface MatchResolution {
  version: number
  decision: 'selected' | 'rejected'
  po_id: string | null
  note: string | null
}

export interface LineMatchCandidate {
  po_line_id: string
  description: string | null
  quantity: string | null
  unit_price: string | null
  amount: string | null
}

export interface LineMatchGroup {
  invoice_line_index: number
  sku: string
  candidates: LineMatchCandidate[]
}

export interface HistoryEvent {
  id: string
  action: string
  event?: string
  field?: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  actor?: string
  created_at: string
  timestamp?: string
  reason?: string
  note: string | null
  version: number
  [key: string]: unknown
}

export interface Approval {
  version: number
  hash: string
  approved_at: string
  approved_by: string
}

export interface DocumentDetail extends DocumentSummary {
  pages: Page[]
  fields: Record<string, FieldEvidence>
  lines: InvoiceLine[]
  findings: Finding[]
  matches: MatchProposal[]
  match_resolution: MatchResolution | null
  line_matches: Record<string, string>
  line_match_candidates: LineMatchGroup[]
  history: HistoryEvent[]
  approval: Approval | null
}

export interface UploadItem {
  document_id: string | null
  job_id: string | null
  status: string
  error: string | null
  filename?: string | null
  deduplicated: boolean
}

export interface UploadResponse {
  items: UploadItem[]
}

export interface Job {
  id: string
  document_id: string
  status: string
  progress: number
  current_page: number
  total_pages: number
  error: string | null
  created_at: string
  updated_at: string
}

export interface Vendor {
  id: string
  name: string
  invoice_count: number
}

export interface Settings {
  mode: string
  model_configured: boolean
  ocr_available: boolean
  workspace_name: string
  export_formats: string[]
}
