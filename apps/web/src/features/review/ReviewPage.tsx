import { useCallback, useRef, useState, type PointerEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ArrowLeft, ChevronRight, Columns2, FileText, RotateCcw } from 'lucide-react'
import { api } from '../../api/client'
import type { Finding } from '../../api/types'
import { ErrorState, LoadingState, StatusPill } from '../../components/States'
import { displayError, downloadBlob, formatMoney, initials, kindLabel, statusLabel, statusTone } from '../../lib/format'
import { SourceViewer } from './SourceViewer'
import { reviewDesignHref, type ReviewDesign } from '../../lib/design-lab'
import { DataPanel, type ReviewTab } from './DataPanel'

export function ReviewPage({ id, design, previewDesign, readOnly, onBack }: { id: string; design?: ReviewDesign; previewDesign?: ReviewDesign; readOnly: boolean; onBack: () => void }) {
  const queryClient = useQueryClient()
  const workbenchRef = useRef<HTMLDivElement>(null)
  const [split, setSplit] = useState(design === 'command' ? 60 : design === 'studio' ? 56 : 54)
  const [mobilePane, setMobilePane] = useState<'source' | 'record'>('record')
  const [tab, setTab] = useState<ReviewTab>(design === 'command' ? 'findings' : 'record')
  const [selectedField, setSelectedField] = useState<string | null>(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [decisionPendingId, setDecisionPendingId] = useState<string | null>(null)
  const [matchPendingId, setMatchPendingId] = useState<string | null>(null)
  const [lineMatchPendingIndex, setLineMatchPendingIndex] = useState<number | null>(null)
  const [exportPending, setExportPending] = useState<string | null>(null)
  const [exportError, setExportError] = useState<unknown>(null)
  const detail = useQuery({ queryKey: ['document', id], queryFn: () => api.document(id), refetchInterval: (query) => ['queued', 'processing'].includes(query.state.data?.status || '') ? 3000 : false })
  const refresh = (next?: unknown) => {
    if (next) queryClient.setQueryData(['document', id], next)
    queryClient.invalidateQueries({ queryKey: ['document', id] })
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['overview'] })
  }
  const correct = useMutation({ mutationFn: ({ field, value, reason }: { field: string; value: string; reason: string }) => api.correct(id, field, value, reason), onSuccess: refresh })
  const revalidate = useMutation({ mutationFn: () => api.revalidate(id), onSuccess: refresh })
  const decide = useMutation({ mutationFn: ({ findingId, decision }: { findingId: string; decision: 'accepted' | 'rejected' }) => api.decideFinding(id, findingId, decision, ''), onSuccess: refresh, onSettled: () => setDecisionPendingId(null) })
  const decideMatch = useMutation({ mutationFn: ({ version, decision, poId, note }: { version: number; decision: 'selected' | 'rejected'; poId: string | null; note: string }) => api.decideMatch(id, version, decision, poId, note), onSuccess: refresh, onSettled: () => setMatchPendingId(null) })
  const decideLineMatch = useMutation({ mutationFn: ({ version, index, poLineId, note }: { version: number; index: number; poLineId: string; note: string }) => api.decideLineMatch(id, version, index, poLineId, note), onSuccess: refresh, onSettled: () => setLineMatchPendingIndex(null) })
  const approve = useMutation({ mutationFn: (version: number) => api.approve(id, version), onSuccess: refresh })
  const onCorrect = async (field: string, value: string, reason: string): Promise<boolean> => { try { await correct.mutateAsync({ field, value, reason }); return true } catch { return false } }
  const onDecide = (finding: Finding, decision: 'accepted' | 'rejected') => { setDecisionPendingId(finding.id); decide.mutate({ findingId: finding.id, decision }) }
  const onDecideMatch = (decision: 'selected' | 'rejected', poId: string | null, note: string) => { setMatchPendingId(poId || 'reject-all'); decideMatch.mutate({ version: detail.data?.version || 0, decision, poId, note }) }
  const onDecideLineMatch = (index: number, poLineId: string, note: string) => { setLineMatchPendingIndex(index); decideLineMatch.mutate({ version: detail.data?.version || 0, index, poLineId, note }) }
  const onExport = async (format: 'csv' | 'xlsx' | 'json') => {
    if (readOnly) { setExportError(new Error('Viewer access cannot download exports. Ask an operator for an approved file.')); return }
    setExportPending(format); setExportError(null)
    try {
      const blob = await api.export(id, format)
      const stem = detail.data?.filename.replace(/\.[^.]+$/, '') || 'invoice'
      downloadBlob(blob, `${stem}-approved-v${detail.data?.version || 1}.${format}`)
      queryClient.invalidateQueries({ queryKey: ['overview'] })
    } catch (error) { setExportError(error) } finally { setExportPending(null) }
  }
  const startResize = (event: PointerEvent<HTMLDivElement>) => {
    if (window.matchMedia('(max-width: 1000px)').matches) return
    event.preventDefault()
    const divider = event.currentTarget
    divider.setPointerCapture(event.pointerId)
    const move = (pointer: globalThis.PointerEvent) => {
      const rect = workbenchRef.current?.getBoundingClientRect()
      if (!rect) return
      setSplit(Math.max(34, Math.min(68, design === 'studio' ? (1 - (pointer.clientX - rect.left) / rect.width) * 100 : (pointer.clientX - rect.left) / rect.width * 100)))
    }
    const stop = () => { divider.removeEventListener('pointermove', move); divider.removeEventListener('pointerup', stop); divider.removeEventListener('pointercancel', stop) }
    divider.addEventListener('pointermove', move)
    divider.addEventListener('pointerup', stop)
    divider.addEventListener('pointercancel', stop)
  }
  const changePage = useCallback((page: number) => setPageNumber(page), [])
  if (detail.isPending) return <main className="page"><LoadingState label="Opening source and extracted record…" /></main>
  if (detail.isError) return <main className="page"><button className="text-action back-link" onClick={onBack}><ArrowLeft size={16} /> Back to queue</button><ErrorState error={detail.error} onRetry={() => detail.refetch()} /></main>
  const document = detail.data
  const openFindings = document.findings.filter((finding) => ['open', 'pending', 'needs_review'].includes(finding.status))
  const firstLineFinding = openFindings.find((finding) => Number.isInteger(finding.details?.invoice_line_index))
  const activeField = selectedField ?? (firstLineFinding ? `lines.${firstLineFinding.details.invoice_line_index}.unit_price` : document.fields.total ? 'total' : null)
  const vendor = document.fields.vendor?.value || document.fields.vendor_name?.value || document.vendor || 'Vendor not extracted'
  const selectedEvidence = activeField?.startsWith('lines.')
    ? (() => { const [, index, property] = activeField.split('.'); return document.lines[Number(index)]?.evidence?.[property] ?? null })()
    : activeField ? document.fields[activeField] ?? null : null
  return <main className={`review-page view-${mobilePane}`} onKeyDown={(event) => { if (event.key === 'Escape' && mobilePane === 'source') { setMobilePane('record'); window.document.querySelector<HTMLButtonElement>('.mobile-review-switch button:last-child')?.focus() } }}>
    <div className="review-topline"><button className="text-action back-link" onClick={onBack}><ArrowLeft size={15} /> Review queue</button><ChevronRight size={13} /><span>{kindLabel(document.kind)}</span><span className="review-file-caption">{document.filename}</span><button className="icon-button review-refresh" disabled={detail.isFetching} onClick={() => detail.refetch()} title="Refresh document" aria-label="Refresh document"><RotateCcw size={15} className={detail.isFetching ? 'spin' : ''} /></button></div>
    <div className="review-header">
      <span className="review-vendor-mark" aria-hidden="true">{initials(String(vendor))}</span>
      <div className="review-title">{design && <span className="design-masthead-eyebrow">{design === 'command' ? 'DOCUMENT COMMAND' : 'INVOICE / REVIEW EDITION'}</span>}<h1>{design === 'studio' ? document.fields.number?.value || document.number || document.filename : vendor}</h1><div className="review-meta">{design === 'studio' && <strong>{vendor}</strong>}<span>{kindLabel(document.kind)} {document.fields.number?.value || document.fields.invoice_number?.value || document.number || document.filename}</span><span className="review-meta-dot" /><span>Version {document.version}</span><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></div></div>
      <div className="review-amount"><strong>{formatMoney(document.fields.total?.value ?? document.total, document.fields.currency?.value ?? document.currency)}</strong><span>{document.fields.currency?.value || document.currency || 'Currency unavailable'} · Stated total</span></div>
      {!readOnly && document.version > 0 && !['queued', 'processing', 'failed', 'cancelled'].includes(document.status) && <button className="button button-secondary review-revalidate" disabled={revalidate.isPending} onClick={() => revalidate.mutate()}><RotateCcw size={14} className={revalidate.isPending ? 'spin' : ''} /> {revalidate.isPending ? 'Checking…' : 'Revalidate'}</button>}
    </div>
    {openFindings.length > 0 && <div className="review-attention"><AlertCircle size={15} /><span><strong>{openFindings.length} open finding{openFindings.length === 1 ? '' : 's'}</strong><span className="attention-description">{openFindings[0].message}</span></span><button onClick={() => { setTab('findings'); setMobilePane('record') }}>Review finding{openFindings.length === 1 ? '' : 's'}<ChevronRight size={14} /></button></div>}
    {revalidate.isError && <div className="notice notice-red" role="alert">{displayError(revalidate.error)}</div>}
    {['queued', 'processing'].includes(document.status) && <div className="notice notice-blue"><RotateCcw size={17} /> Extraction is still running. This view will refresh as pages complete.</div>}
    {document.status === 'failed' && <div className="notice notice-red"><FileText size={17} /> Processing failed. Open Batch intake to inspect the job error and retry.</div>}
    <div className="mobile-review-switch" role="group" aria-label="Review panel"><button aria-pressed={mobilePane === 'source'} onClick={() => setMobilePane('source')}>Document</button><button aria-pressed={mobilePane === 'record'} onClick={() => setMobilePane('record')}>Details</button></div>
    <div className={'workbench mobile-pane-' + mobilePane} ref={workbenchRef} style={{ '--source-width': `${split}%` } as React.CSSProperties}>
      <SourceViewer document={document} selectedField={activeField} selectedEvidence={selectedEvidence} pageNumber={pageNumber} onPageChange={changePage} />
      <div className="panel-resizer" role="separator" tabIndex={0} aria-label="Resize source and data panels" aria-orientation="vertical" aria-valuenow={split} aria-valuemin={34} aria-valuemax={68} onPointerDown={startResize} onKeyDown={(event) => { if (event.key === 'ArrowLeft') { event.preventDefault(); setSplit((value) => Math.max(34, value + (design === 'studio' ? 3 : -3))) } if (event.key === 'ArrowRight') { event.preventDefault(); setSplit((value) => Math.min(68, value + (design === 'studio' ? -3 : 3))) } }}><Columns2 size={15} /></div>
      <DataPanel design={design} tab={tab} onTabChange={setTab} document={document} selectedField={activeField} onSelectField={(field) => { setSelectedField(field); if (window.matchMedia('(max-width: 1000px)').matches) { setMobilePane('source'); workbenchRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) } }} onOpenMatch={(matchedId) => { window.location.hash = reviewDesignHref(matchedId, previewDesign) }} readOnly={readOnly} onCorrect={onCorrect} correctionPending={correct.isPending} correctionError={correct.error} onDecide={onDecide} decisionPendingId={decisionPendingId} decisionError={decide.error} onDecideMatch={onDecideMatch} matchPendingId={matchPendingId} matchDecisionError={decideMatch.error} onDecideLineMatch={onDecideLineMatch} lineMatchPendingIndex={lineMatchPendingIndex} lineMatchDecisionError={decideLineMatch.error} onApprove={() => approve.mutate(document.version)} approvalPending={approve.isPending} approvalError={approve.error} onExport={onExport} exportPending={exportPending} exportError={exportError} />
    </div>
    {correct.isSuccess && <div className="sr-only" role="status">Correction saved and validation rerun.</div>}
    {approve.isSuccess && <div className="sr-only" role="status">Document version approved.</div>}
    {decide.isSuccess && <div className="sr-only" role="status">Review decision recorded.</div>}
    {decideMatch.isSuccess && <div className="sr-only" role="status">Purchase order decision recorded.</div>}
    {decideLineMatch.isSuccess && <div className="sr-only" role="status">Purchase order line mapping recorded.</div>}
    {Boolean(exportError) && <div className="sr-only" role="alert">{displayError(exportError)}</div>}
  </main>
}
