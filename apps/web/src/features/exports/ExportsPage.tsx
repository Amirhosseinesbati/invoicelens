import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Download, FileJson2, FileSpreadsheet, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { displayError, downloadBlob, formatDate, formatMoney, kindLabel, statusLabel, statusTone } from '../../lib/format'

export function ExportsPage({ readOnly, onOpenDocument }: { readOnly: boolean; onOpenDocument: (id: string) => void }) {
  const documents = useQuery({ queryKey: ['documents'], queryFn: api.documents })
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const download = async (id: string, filename: string, version: number, format: 'csv' | 'xlsx' | 'json') => {
    if (readOnly) { setError('Viewer access cannot download exports. Ask an operator for an approved file.'); return }
    setError(null); setPending(`${id}:${format}`)
    try { downloadBlob(await api.export(id, format), `${filename.replace(/\.[^.]+$/, '')}-approved-v${version}.${format}`); queryClient.invalidateQueries({ queryKey: ['overview'] }) }
    catch (failure) { setError(displayError(failure)) }
    finally { setPending(null) }
  }
  if (documents.isPending) return <main className="page"><LoadingState label="Loading approved documents…" /></main>
  if (documents.isError) return <main className="page"><ErrorState error={documents.error} onRetry={() => documents.refetch()} /></main>
  const approved = documents.data.filter((document) => document.status === 'approved').sort((a, b) => b.created_at.localeCompare(a.created_at))
  return <main className="page exports-page"><div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> ACCOUNTING HANDOFF</span><h1>Approved exports<span className="title-period">.</span></h1><p>Download an accounting-ready record only after its exact version is approved.</p></div><div className="head-count"><strong>{approved.length}</strong><span>ready records</span></div></div>
    <div className="export-info"><ShieldCheck size={20} /><div><strong>Version-bound downloads</strong><p>Any correction invalidates prior approval. CSV cells are escaped on the server to prevent spreadsheet formulas.</p></div></div>
    {readOnly && <p className="form-hint">Viewer access can inspect approved records. An operator must download the accounting export.</p>}
    {error && <div className="inline-error" role="alert">{error}</div>}
    <section className="surface exports-surface"><div className="section-heading"><div><span className="section-kicker">READY FOR HANDOFF</span><h2>Document register</h2></div><span className="export-formats"><FileSpreadsheet size={15} /> XLSX / CSV <FileJson2 size={15} /> JSON</span></div>{approved.length ? <div className="table-scroll"><table className="data-table export-table"><thead><tr><th>Document</th><th>Vendor</th><th>Amount</th><th>Version</th><th>Status</th><th>Download</th></tr></thead><tbody>{approved.map((document) => <tr key={document.id}><td><button className="table-link" onClick={() => onOpenDocument(document.id)}><strong>{document.number || document.filename}</strong><small>{kindLabel(document.kind)} · {formatDate(document.date)}</small></button></td><td>{document.vendor || '—'}</td><td className="number-cell">{formatMoney(document.total, document.currency)}</td><td>v{document.version}</td><td><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></td><td><div className="export-row-actions"><button onClick={() => download(document.id, document.filename, document.version, 'xlsx')} disabled={readOnly || Boolean(pending)} title="Download XLSX"><Download size={14} /> XLSX</button><button onClick={() => download(document.id, document.filename, document.version, 'csv')} disabled={readOnly || Boolean(pending)} title="Download CSV">CSV</button><button onClick={() => download(document.id, document.filename, document.version, 'json')} disabled={readOnly || Boolean(pending)} title="Download JSON">JSON</button><button className="icon-button" onClick={() => onOpenDocument(document.id)} aria-label={`Open ${document.filename}`}><ArrowUpRight size={15} /></button></div></td></tr>)}</tbody></table></div> : <EmptyState title="No approved records yet" description="Review a document, resolve its findings, and approve its current version to enable downloads." />}</section>
  </main>
}
