import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, ArrowUpRight, Check, FileCheck2, FileWarning, Layers3, ScanLine, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import type { DocumentSummary } from '../../api/types'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { useWorkspace } from '../../components/WorkspaceProvider'
import { formatDate, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'
import { inQueueView, selectDocuments } from '../../lib/queue'

function PriorityRow({ document, onOpen }: { document: DocumentSummary; onOpen: (id: string) => void }) {
  return <button className="priority-row" onClick={() => onOpen(document.id)}>
    <span className="vendor-monogram">{initials(document.vendor)}</span>
    <span className="priority-main"><strong>{document.vendor || document.filename}</strong><small>{kindLabel(document.kind)} · {document.number || 'Number pending'} · {formatDate(document.date)}</small></span>
    <span className="priority-amount">{formatMoney(document.total, document.currency)}<small>{document.findings_count} finding{document.findings_count === 1 ? '' : 's'}</small></span>
    <ArrowUpRight size={18} className="priority-arrow" />
  </button>
}

export function OverviewPage({ onOpenDocument, onNavigate }: { onOpenDocument: (id: string) => void; onNavigate: (view: string) => void }) {
  const { workspaceName } = useWorkspace()
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.overview, refetchInterval: 15_000 })
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents, refetchInterval: 15_000 })
  if (overview.isPending || documents.isPending) return <main className="page"><LoadingState label="Loading the operations overview…" /></main>
  if (overview.isError) return <main className="page"><ErrorState error={overview.error} onRetry={() => overview.refetch()} /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  const review = selectDocuments(documents.data, 'needs_review', '', 'all', 'priority')
  const recent = selectDocuments(documents.data, 'all', '', 'all', 'newest').slice(0, 6)
  const retryCount = documents.data.filter((item) => inQueueView(item, 'failed')).length
  const activeCount = documents.data.filter((item) => inQueueView(item, 'processing')).length
  const approvedCount = documents.data.filter((item) => item.status === 'approved').length
  const stages = [
    { label: 'In processing', count: activeCount, tone: 'blue', route: 'queue?status=processing' },
    { label: 'Needs review', count: review.length, tone: 'amber', route: 'queue?status=needs_review' },
    { label: 'Approved', count: approvedCount, tone: 'green', route: 'queue?status=approved' },
    { label: 'Needs retry', count: retryCount, tone: 'red', route: 'queue?status=failed' },
  ]
  const otherCount = documents.data.length - stages.reduce((sum, stage) => sum + stage.count, 0)
  const next = review[0]
  return <main className="page overview-page">
    <div className="overview-heading"><div><span className="eyebrow"><span className="eyebrow-line" /> OPERATIONS DESK</span><span className="workspace-heading">{workspaceName}</span></div><button className="button button-secondary" onClick={() => onNavigate('intake')}><ScanLine size={16} /> Add documents</button></div>
    <section className="operations-hero"><div className="hero-copy"><span className="hero-index">CURRENT WORKLOAD</span><h1>Review command.<br /><em>Every decision, traceable.</em></h1><p>Prioritize exceptions, inspect original evidence and prepare reviewed records for handoff.</p><div className="hero-trust"><ShieldCheck size={16} /> Human review before accounting handoff</div></div>
      <div className="next-review"><span className="section-kicker">YOUR NEXT MOVE</span>{next ? <><div className="next-review-title"><span className="vendor-monogram">{initials(next.vendor)}</span><div><strong>{next.vendor || next.filename}</strong><small>{next.number || next.filename}</small></div></div><div className="next-review-facts"><span>{next.findings_count} finding{next.findings_count === 1 ? '' : 's'} to inspect</span><strong>{formatMoney(next.total, next.currency)}</strong></div><p>Start with the record with the most findings. Inspect the source before making a decision.</p><button className="button button-primary" onClick={() => onOpenDocument(next.id)}>Continue review <ArrowRight size={17} /></button></> : <><div className="next-clear"><FileCheck2 size={30} /><h2>{documents.data.length ? 'The review queue is clear.' : 'Your workspace is ready.'}</h2></div><p>{documents.data.length ? 'Check approved records for handoff, or add your next batch.' : 'Add invoices and purchase orders to begin an evidence-backed review.'}</p><button className="button button-primary" onClick={() => onNavigate(approvedCount ? 'exports' : 'intake')}>{approvedCount ? 'Prepare handoff' : 'Add first batch'} <ArrowRight size={17} /></button></>}</div>
    </section>
    {retryCount > 0 && <div className="retry-notice"><AlertTriangle size={19} /><div><strong>{retryCount} document{retryCount === 1 ? '' : 's'} need another look</strong><p>Processing failed or was cancelled. Inspect the job before retrying.</p></div><button className="text-action" onClick={() => onNavigate('queue?status=failed')}>Inspect records <ArrowRight size={16} /></button></div>}
    <div className="overview-metrics" aria-label="Current workload">
      <div className="metric metric-featured"><span>01 / ATTENTION</span><div><strong>{review.length}</strong><FileWarning size={25} /></div><p>Documents need review</p><button onClick={() => onNavigate('queue?status=needs_review')}>Open review queue <ArrowRight size={15} /></button></div>
      <div className="metric"><span>02 / ACTIVE</span><div><strong>{activeCount}</strong><Layers3 size={24} /></div><p>In processing</p><button onClick={() => onNavigate('intake')}>View batch progress <ArrowRight size={15} /></button></div>
      <div className="metric"><span>03 / CLEARED</span><div><strong>{approvedCount}</strong><FileCheck2 size={24} /></div><p>Approved documents</p><button onClick={() => onNavigate('exports')}>View ready exports <ArrowRight size={15} /></button></div>
    </div>
    <section className="surface flow-surface" aria-label="Document workflow"><div className="flow-heading"><div><span className="section-kicker">WORKSPACE SNAPSHOT</span><h2>Where the work stands</h2></div><span>{documents.data.length} documents</span></div><div className="flow-bar" aria-hidden="true">{stages.filter((stage) => stage.count > 0).map((stage) => <span key={stage.label} className={'flow-' + stage.tone} style={{ flex: stage.count }} />)}{otherCount > 0 && <span className="flow-neutral" style={{ flex: otherCount }} />}</div><div className="flow-stages">{stages.map((stage) => <button key={stage.label} onClick={() => onNavigate(stage.route)}><span className={'flow-dot flow-' + stage.tone} /><span>{stage.label}</span><strong>{stage.count}</strong><ArrowUpRight size={14} /></button>)}{otherCount > 0 && <button onClick={() => onNavigate('queue?status=all')}><span className="flow-dot flow-neutral" /><span>Other states</span><strong>{otherCount}</strong></button>}</div></section>
    <div className="overview-grid">
      <section className="surface priority-surface"><div className="section-heading"><div><span className="section-kicker">PRIORITY WORK</span><h2>Exceptions to resolve <span className="heading-count">{overview.data.findings_open}</span></h2></div><button className="text-action" onClick={() => onNavigate('queue?status=needs_review')}>Full queue <ArrowRight size={16} /></button></div>
        {review.length ? <div className="priority-list">{review.slice(0, 5).map((document) => <PriorityRow key={document.id} document={document} onOpen={onOpenDocument} />)}</div> : <EmptyState title="The queue is clear" description="Documents that need attention will appear here after intake and validation." action="Upload documents" onAction={() => onNavigate('intake')} />}
      </section>
      <aside className="desk-aside"><section className="surface desk-summary"><span className="section-kicker">AT A GLANCE</span><h2>{documents.data.length} <small>documents</small></h2><div className="summary-line"><span>Open findings</span><strong>{overview.data.findings_open}</strong></div><div className="summary-line"><span>Vendors represented</span><strong>{overview.data.vendors}</strong></div><div className="summary-line"><span>Exports prepared</span><strong>{overview.data.export_count}</strong></div></section><div className="review-protocol"><span className="section-kicker">REVIEW PROTOCOL</span><h3>A record you can trace.</h3><ol><li><Check size={14} /> Compare fields with the source</li><li><Check size={14} /> Inspect totals and PO mappings</li><li><Check size={14} /> Resolve open findings</li><li><Check size={14} /> Approve the current version</li></ol><small>Extraction quality depends on the source and adapter. Keep the operator in the loop.</small></div></aside>
    </div>
    <section className="surface recent-surface"><div className="section-heading"><div><span className="section-kicker">DOCUMENT REGISTER</span><h2>Recently handled</h2></div><button className="text-action" onClick={() => onNavigate('queue?status=all')}>All documents <ArrowRight size={16} /></button></div>
      {recent.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>Document</th><th>Vendor</th><th>Received</th><th>Amount</th><th>Status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{recent.map((document) => <tr key={document.id}><td><button className="table-link" onClick={() => onOpenDocument(document.id)}><strong>{document.number || document.filename}</strong><small>{kindLabel(document.kind)}</small></button></td><td>{document.vendor || 'Pending extraction'}</td><td>{formatDate(document.created_at)}</td><td className="number-cell">{formatMoney(document.total, document.currency)}</td><td><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></td><td><button className="icon-button" aria-label={'Open ' + document.filename} onClick={() => onOpenDocument(document.id)}><ArrowUpRight size={17} /></button></td></tr>)}</tbody></table></div> : <EmptyState title="No documents yet" description="Start with a batch of PDF, PNG, or JPEG files." action="Go to batch intake" onAction={() => onNavigate('intake')} />}
    </section>
  </main>
}
