import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, FileSearch2, Filter, Search } from 'lucide-react'
import { api } from '../../api/client'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { formatDate, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'

const filters = [
  { id: 'needs_review', label: 'Needs review' },
  { id: 'all', label: 'All documents' },
  { id: 'processing', label: 'Processing' },
  { id: 'approved', label: 'Approved' },
  { id: 'failed', label: 'Failed' },
] as const

export function QueuePage({ search, onOpenDocument }: { search: string; onOpenDocument: (id: string) => void }) {
  const [filter, setFilter] = useState<string>('needs_review')
  const [localSearch, setLocalSearch] = useState('')
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents, refetchInterval: 10_000 })
  const filtered = useMemo(() => {
    const needle = (localSearch || search).trim().toLowerCase()
    return (documents.data || []).filter((document) => (filter === 'all' || document.status === filter) && (!needle || [document.filename, document.vendor, document.number, document.kind].some((value) => value?.toLowerCase().includes(needle)))).sort((a, b) => b.created_at.localeCompare(a.created_at))
  }, [documents.data, filter, localSearch, search])
  if (documents.isPending) return <main className="page"><LoadingState label="Loading the review queue…" /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  return <main className="page queue-page">
    <div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> DOCUMENT OPERATIONS</span><h1>Review queue<span className="title-period">.</span></h1><p>Open a record to compare its extracted data against the original source.</p></div><div className="head-count"><strong>{documents.data.length}</strong><span>total documents</span></div></div>
    <section className="surface queue-surface"><div className="queue-toolbar"><div className="filter-tabs" role="group" aria-label="Filter documents">{filters.map((item) => <button key={item.id} className={filter === item.id ? 'filter-active' : ''} onClick={() => setFilter(item.id)}>{item.label}{item.id === 'needs_review' && <b>{documents.data.filter((doc) => doc.status === 'needs_review').length}</b>}</button>)}</div><label className="queue-search"><Search size={16} /><input aria-label="Filter queue" placeholder="Filter by vendor or number" value={localSearch || search} onChange={(event) => setLocalSearch(event.target.value)} /></label></div>
      <div className="queue-caption"><Filter size={14} /> Showing {filtered.length} of {documents.data.length} documents</div>
      {filtered.length ? <div className="queue-list">{filtered.map((document) => <button key={document.id} className="queue-item" onClick={() => onOpenDocument(document.id)}><span className="vendor-monogram">{initials(document.vendor)}</span><span className="queue-item-main"><strong>{document.vendor || 'Vendor pending'}</strong><small>{kindLabel(document.kind)} <span>·</span> {document.number || document.filename}</small></span><span className="queue-item-date">{formatDate(document.date || document.created_at)}<small>{document.page_count} page{document.page_count === 1 ? '' : 's'}</small></span><span className="queue-item-amount">{formatMoney(document.total, document.currency)}<small>{document.findings_count ? `${document.findings_count} finding${document.findings_count === 1 ? '' : 's'}` : 'No findings'}</small></span><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill><ArrowUpRight size={18} className="queue-item-arrow" /></button>)}</div> : <EmptyState title={filter === 'needs_review' ? 'No documents need review' : 'No matching documents'} description={filter === 'needs_review' ? 'You are caught up. Check all documents or start a new batch.' : 'Try another status or search term.'} action={filter === 'needs_review' ? 'View all documents' : 'Clear filters'} onAction={() => { setFilter('all'); setLocalSearch('') }} />}
    </section>
    <div className="queue-help"><FileSearch2 size={17} /><p>Need to understand a discrepancy? Open the record, select a field, and inspect its linked source evidence.</p><ArrowRight size={16} /></div>
  </main>
}
