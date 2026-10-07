import type { DocumentSummary } from '../api/types.ts'
import type { QueueView } from './workspace-profile.ts'

export type QueueSort = 'priority' | 'newest' | 'oldest' | 'vendor'
export function inQueueView(document: DocumentSummary, view: QueueView): boolean {
  if (view === 'all') return true
  if (view === 'processing') return ['uploaded', 'queued', 'processing'].includes(document.status)
  if (view === 'failed') return ['failed', 'cancelled'].includes(document.status)
  return document.status === view
}

export function selectDocuments(documents: DocumentSummary[], view: QueueView, search: string, kind: string, sort: QueueSort): DocumentSummary[] {
  const needle = search.trim().toLocaleLowerCase()
  return documents.filter((item) => inQueueView(item, view) && (kind === 'all' || item.kind === kind) && (!needle || [item.filename, item.vendor, item.number, item.kind.replace(/_/g, ' ')].some((value) => value?.toLocaleLowerCase().includes(needle))))
    .sort((a, b) => {
      if (sort === 'priority') return b.findings_count - a.findings_count || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
      if (sort === 'oldest') return a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
      if (sort === 'vendor') return (a.vendor || '').localeCompare(b.vendor || '') || b.created_at.localeCompare(a.created_at)
      return b.created_at.localeCompare(a.created_at) || a.id.localeCompare(b.id)
    })
}

export function queueViewFromHash(hash: string, fallback: QueueView): QueueView {
  const view = new URLSearchParams(hash.split('?')[1] || '').get('status')
  return ['needs_review', 'all', 'processing', 'approved', 'failed'].includes(view || '') ? view as QueueView : fallback
}
