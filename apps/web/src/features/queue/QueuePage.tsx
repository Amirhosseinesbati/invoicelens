import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, FileSearch2, Search, SlidersHorizontal, X } from 'lucide-react'
import { api } from '../../api/client'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { formatDate, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'
import { inQueueView, selectDocuments, type QueueSort } from '../../lib/queue'
import type { QueueView } from '../../lib/workspace-profile'

const filters = [
  { id: 'needs_review', label: 'Needs review' }, { id: 'all', label: 'All documents' },
  { id: 'processing', label: 'Processing' }, { id: 'approved', label: 'Approved' }, { id: 'failed', label: 'Needs retry' },
] as const

export function QueuePage({ search, onSearch, initialView, onOpenDocument, onNavigate }: {
  search: string; onSearch: (value: string) => void; initialView: QueueView; onOpenDocument: (id: string) => void; onNavigate: (view: string) => void
}) {
  const [filter, setFilter] = useState<QueueView>(initialView)
  const [kind, setKind] = useState('all')
  const [sort, setSort] = useState<QueueSort>('priority')
  const [limit, setLimit] = useState(25)
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents, refetchInterval: 10_000 })
  const filtered = useMemo(() => selectDocuments(documents.data || [], filter, search, kind, sort), [documents.data, filter, search, kind, sort])
  const clear = () => { setFilter('all'); setKind('all'); onSearch(''); setLimit(25) }
  if (documents.isPending) return <main className="page"><LoadingState label="Loading the review queue…" /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  return <main className="page queue-page">
    <div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> DOCUMENT OPERATIONS</span><h1>Review queue</h1><p>Prioritize findings, inspect the source, and move reviewed records toward handoff.</p></div><button className="button button-primary" onClick={() => onNavigate('intake')}>Add documents <ArrowRight size={16} /></button></div>
    <section className="surface queue-surface" aria-label="Document queue">
      <div className="queue-toolbar"><div className="filter-tabs" role="group" aria-label="Filter documents">{filters.map((item) => <button key={item.id} aria-pressed={filter === item.id} className={filter === item.id ? 'filter-active' : ''} onClick={() => { setFilter(item.id); setLimit(25) }}>{item.label}<b>{documents.data.filter((doc) => inQueueView(doc, item.id)).length}</b></button>)}</div></div>
      <div className="queue-controls"><label className="queue-search"><Search size={17} /><input aria-label="Filter queue" placeholder="Vendor, document number, or filename" value={search} onChange={(event) => { onSearch(event.target.value); setLimit(25) }} />{search && <button className="icon-button" onClick={() => onSearch('')} aria-label="Clear search"><X size={15} /></button>}</label><label className="select-field"><span>Document type</span><select value={kind} onChange={(event) => { setKind(event.target.value); setLimit(25) }}><option value="all">All types</option><option value="invoice">Invoices</option><option value="purchase_order">Purchase orders</option><option value="credit_note">Credit notes</option><option value="unknown">Unclassified</option></select></label><label className="select-field"><span>Sort by</span><select value={sort} onChange={(event) => setSort(event.target.value as QueueSort)}><option value="priority">Most findings first</option><option value="oldest">Oldest received</option><option value="newest">Newest received</option><option value="vendor">Vendor name</option></select></label></div>
      <div className="queue-caption"><SlidersHorizontal size={14} /><span role="status">{filtered.length} matching / {documents.data.length} total</span>{(search || kind !== 'all') && <button className="text-action" onClick={clear}>Clear filters</button>}<span className="queue-caption-note">Amounts stay in their original currency</span></div>
      {filtered.length ? <div className="queue-list">{filtered.slice(0, limit).map((document) => <button key={document.id} className="queue-item" onClick={() => onOpenDocument(document.id)}><span className="vendor-monogram">{initials(document.vendor)}</span><span className="queue-item-main"><strong>{document.vendor || 'Vendor pending'}</strong><small>{kindLabel(document.kind)} <span>·</span> {document.number || document.filename}</small></span><span className="queue-item-date">{formatDate(document.date || document.created_at)}<small>{document.page_count} page{document.page_count === 1 ? '' : 's'} · v{document.version}</small></span><span className="queue-item-amount">{formatMoney(document.total, document.currency)}<small>{document.findings_count ? `${document.findings_count} finding${document.findings_count === 1 ? '' : 's'}` : 'No findings'}</small></span><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill><ArrowUpRight size={18} className="queue-item-arrow" /></button>)}</div> : <EmptyState title={!documents.data.length ? 'Your document desk is ready' : search || kind !== 'all' ? 'No documents match these filters' : filter === 'needs_review' ? 'Nothing waiting for review' : 'No documents in this stage'} description={!documents.data.length ? 'Add your first batch of invoices and purchase orders to start a traceable review.' : 'Search applies within the selected stage. View all documents to broaden the results.'} action={!documents.data.length ? 'Add first batch' : 'View all documents'} onAction={!documents.data.length ? () => onNavigate('intake') : clear} />}
      {filtered.length > limit && <div className="queue-more"><span>Showing {limit} of {filtered.length}</span><button className="button button-secondary" onClick={() => setLimit((value) => value + 25)}>Show 25 more <ArrowRight size={15} /></button></div>}
    </section>
    {filter === 'failed' ? <div className="queue-help"><FileSearch2 size={19} /><p>Failed and cancelled documents stay in the register. Open batch activity to inspect the error and retry processing.</p><button className="text-action" onClick={() => onNavigate('intake')}>Batch activity <ArrowRight size={16} /></button></div> : <div className="queue-help"><FileSearch2 size={19} /><p>Review a field’s source evidence, resolve findings and PO mappings, then approve the current version.</p></div>}
  </main>
}
