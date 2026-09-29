import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, FileCheck2, FileWarning, Layers3, ScanLine } from 'lucide-react'
import { api } from '../../api/client'
import type { DocumentSummary } from '../../api/types'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { formatDate, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'

function PriorityRow({ document, onOpen }: { document: DocumentSummary; onOpen: (id: string) => void }) {
  return <button className="priority-row" onClick={() => onOpen(document.id)}>
    <span className="vendor-monogram">{initials(document.vendor)}</span>
    <span className="priority-main"><strong>{document.vendor || document.filename}</strong><small>{kindLabel(document.kind)} <span>·</span> {document.number || 'Number pending'} <span>·</span> {formatDate(document.date)}</small></span>
    <span className="priority-amount">{formatMoney(document.total, document.currency)}<small>{document.findings_count} finding{document.findings_count === 1 ? '' : 's'}</small></span>
    <ArrowUpRight size={18} className="priority-arrow" />
  </button>
}

export function OverviewPage({ onOpenDocument, onNavigate }: { onOpenDocument: (id: string) => void; onNavigate: (view: string) => void }) {
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.overview, refetchInterval: 15_000 })
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents, refetchInterval: 15_000 })
  if (overview.isPending || documents.isPending) return <main className="page"><LoadingState label="Loading the operations overview…" /></main>
  if (overview.isError) return <main className="page"><ErrorState error={overview.error} onRetry={() => overview.refetch()} /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  const review = documents.data.filter((document) => document.status === 'needs_review').sort((a, b) => b.findings_count - a.findings_count || b.created_at.localeCompare(a.created_at))
  const recent = [...documents.data].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 6)
  return <main className="page overview-page">
    <div className="page-head"><div><span className="eyebrow"><span className="eyebrow-line" /> OPERATIONS DESK</span><h1>Good work starts<br /><em>with a clear queue.</em></h1><p>Track documents, investigate exceptions, and approve evidence-backed records.</p></div><button className="button button-primary" onClick={() => onNavigate('intake')}><ScanLine size={17} /> New batch <ArrowRight size={17} /></button></div>
    <div className="overview-metrics" aria-label="Current workload">
      <div className="metric metric-featured"><span>01 / ATTENTION</span><div><strong>{overview.data.needs_review}</strong><FileWarning size={25} /></div><p>Documents need review</p><button onClick={() => onNavigate('queue')}>Open review queue <ArrowRight size={15} /></button></div>
      <div className="metric"><span>02 / ACTIVE</span><div><strong>{overview.data.processing}</strong><Layers3 size={24} /></div><p>In processing</p><button onClick={() => onNavigate('intake')}>View batch progress <ArrowRight size={15} /></button></div>
      <div className="metric"><span>03 / CLEARED</span><div><strong>{overview.data.approved}</strong><FileCheck2 size={24} /></div><p>Approved documents</p><button onClick={() => onNavigate('exports')}>View ready exports <ArrowRight size={15} /></button></div>
    </div>
    <div className="overview-grid">
      <section className="surface priority-surface"><div className="section-heading"><div><span className="section-kicker">PRIORITY WORK</span><h2>Exceptions to resolve <span className="heading-count">{overview.data.findings_open}</span></h2></div><button className="text-action" onClick={() => onNavigate('queue')}>View full queue <ArrowRight size={16} /></button></div>
        {review.length ? <div className="priority-list">{review.slice(0, 5).map((document) => <PriorityRow key={document.id} document={document} onOpen={onOpenDocument} />)}</div> : <EmptyState title="The queue is clear" description="Documents that need attention will appear here after intake and validation." action="Upload documents" onAction={() => onNavigate('intake')} />}
      </section>
      <aside className="desk-aside"><section className="surface desk-summary"><span className="section-kicker">AT A GLANCE</span><h2>{overview.data.total_documents} <small>documents</small></h2><div className="summary-line"><span>Open findings</span><strong>{overview.data.findings_open}</strong></div><div className="summary-line"><span>Vendors represented</span><strong>{overview.data.vendors}</strong></div><div className="summary-line"><span>Exports prepared</span><strong>{overview.data.export_count}</strong></div></section><div className="aside-quote"><span>FIELD NOTE / 001</span><p>“A reliable record begins with a traceable source.”</p><small>Every extracted value remains linked to its source page when evidence is available.</small></div></aside>
    </div>
    <section className="surface recent-surface"><div className="section-heading"><div><span className="section-kicker">DOCUMENT REGISTER</span><h2>Recently handled</h2></div><button className="text-action" onClick={() => onNavigate('queue')}>All documents <ArrowRight size={16} /></button></div>
      {recent.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Document</th><th>Vendor</th><th>Received</th><th>Amount</th><th>Status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{recent.map((document) => <tr key={document.id}><td><button className="table-link" onClick={() => onOpenDocument(document.id)}><strong>{document.number || document.filename}</strong><small>{kindLabel(document.kind)}</small></button></td><td>{document.vendor || 'Pending extraction'}</td><td>{formatDate(document.created_at)}</td><td className="number-cell">{formatMoney(document.total, document.currency)}</td><td><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></td><td><button className="icon-button" aria-label={`Open ${document.filename}`} onClick={() => onOpenDocument(document.id)}><ArrowUpRight size={17} /></button></td></tr>)}</tbody></table></div> : <EmptyState title="No documents yet" description="Start with a batch of PDF, PNG, or JPEG files." action="Go to batch intake" onAction={() => onNavigate('intake')} />}
    </section>
  </main>
}
