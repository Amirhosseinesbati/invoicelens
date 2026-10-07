import type { DocumentDetail, DocumentSummary, Job, LoginResponse, Overview, Settings, UploadResponse, User, Vendor } from './types'

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly details?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => typeof item?.msg === 'string' ? item.msg : String(item)).join('; ')
  }
  if (body && typeof body === 'object' && 'message' in body && typeof (body as { message: unknown }).message === 'string') return (body as { message: string }).message
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(path, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError('The server is unreachable. Check the API connection and retry.', 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as unknown
    throw new ApiError(errorMessage(body, `${response.status} ${response.statusText}`), response.status, body)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function requestBlob(path: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(path, { credentials: 'include' })
  } catch {
    throw new ApiError('The source file is unavailable while the server is disconnected.', 0)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as unknown
    throw new ApiError(errorMessage(body, 'Unable to load the source file.'), response.status, body)
  }
  return response.blob()
}

export const api = {
  health: () => request<{ status: string; mode: string }>('/api/health'),
  login: (email: string, password: string) => request<LoginResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<User>('/api/auth/me'),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  overview: () => request<Overview>('/api/overview'),
  documents: () => request<DocumentSummary[]>('/api/documents'),
  document: (id: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`),
  source: (id: string) => requestBlob(`/api/documents/${encodeURIComponent(id)}/source`),
  pageImage: (id: string, page: number) => requestBlob(`/api/documents/${encodeURIComponent(id)}/pages/${page}/image`),
  upload: (files: File[]) => {
    const body = new FormData()
    files.forEach((file) => body.append('files', file))
    return request<UploadResponse>('/api/uploads', { method: 'POST', body })
  },
  jobs: () => request<Job[]>('/api/jobs'),
  cancelJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  retryJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  correct: (id: string, field: string, value: string, reason: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/corrections`, { method: 'POST', body: JSON.stringify({ field, value, reason }) }),
  revalidate: (id: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/revalidate`, { method: 'POST' }),
  decideFinding: (id: string, findingId: string, decision: 'accepted' | 'rejected', note: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/findings/${encodeURIComponent(findingId)}/decisions`, { method: 'POST', body: JSON.stringify({ decision, note }) }),
  decideMatch: (id: string, version: number, decision: 'selected' | 'rejected', poId: string | null, note: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/matches/decision`, { method: 'POST', body: JSON.stringify({ version, decision, po_id: poId, note }) }),
  decideLineMatch: (id: string, version: number, invoiceLineIndex: number, poLineId: string, note: string) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/line-matches/decision`, { method: 'POST', body: JSON.stringify({ version, invoice_line_index: invoiceLineIndex, po_line_id: poLineId, note }) }),
  approve: (id: string, version: number) => request<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify({ version }) }),
  export: (id: string, format: 'csv' | 'xlsx' | 'json') => requestBlob(`/api/documents/${encodeURIComponent(id)}/exports?format=${format}`),
  vendors: () => request<Vendor[]>('/api/vendors'),
  settings: () => request<Settings>('/api/settings'),
}
