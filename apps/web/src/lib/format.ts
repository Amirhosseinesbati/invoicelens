import type { DocumentKind, DocumentStatus } from '../api/types'

export const fieldLabels: Record<string, string> = {
  vendor: 'Vendor',
  vendor_name: 'Vendor',
  number: 'Document number',
  invoice_number: 'Invoice number',
  po_number: 'PO number',
  document_number: 'Document number',
  date: 'Issue date',
  invoice_date: 'Issue date',
  due_date: 'Due date',
  currency: 'Currency',
  subtotal: 'Subtotal',
  tax: 'Tax',
  freight: 'Freight',
  discount: 'Discount',
  discounts: 'Discounts',
  total: 'Total',
}

export const fieldOrder = ['vendor', 'vendor_name', 'number', 'invoice_number', 'po_number', 'document_number', 'date', 'invoice_date', 'due_date', 'currency', 'subtotal', 'tax', 'freight', 'discount', 'discounts', 'total']

export function labelForField(key: string): string {
  return fieldLabels[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

export function kindLabel(kind: DocumentKind): string {
  return ({ invoice: 'Invoice', purchase_order: 'Purchase order', credit_note: 'Credit note', unknown: 'Unclassified' } as Record<string, string>)[kind] ?? labelForField(kind)
}

export function statusLabel(status: DocumentStatus): string {
  return ({ needs_review: 'Needs review', approved: 'Approved', processing: 'Processing', queued: 'Queued', uploaded: 'Uploaded', failed: 'Failed', cancelled: 'Cancelled', complete: 'Complete', accepted: 'Accepted', rejected: 'Rejected' } as Record<string, string>)[status] ?? labelForField(status)
}

export function statusTone(status: string): 'amber' | 'green' | 'red' | 'blue' | 'neutral' {
  if (status === 'approved' || status === 'completed' || status === 'complete' || status === 'accepted') return 'green'
  if (status === 'needs_review' || status === 'pending' || status === 'open') return 'amber'
  if (status === 'failed' || status === 'cancelled') return 'red'
  if (status === 'processing' || status === 'running' || status === 'queued') return 'blue'
  return 'neutral'
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) return value
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) return value
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date)
}

export function formatMoney(value: string | number | null | undefined, currency?: string | null): string {
  if (value == null || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return String(value)
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency || 'USD' }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${currency ?? ''}`.trim()
  }
}

export function initials(value: string | null | undefined): string {
  return (value ?? 'Unknown').split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U'
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
}

export function displayError(error: unknown): string {
  return error instanceof Error ? error.message : 'An unexpected error occurred. Please retry.'
}
