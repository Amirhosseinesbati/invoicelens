import { useCallback, useRef, useState, type PointerEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowUpRight, Columns2, FileText, RotateCcw } from 'lucide-react'
import { api } from '../../api/client'
import type { Finding } from '../../api/types'
import { ErrorState, LoadingState, StatusPill } from '../../components/States'
import { displayError, downloadBlob, kindLabel, statusLabel, statusTone } from '../../lib/format'
import { SourceViewer } from './SourceViewer'
import { DataPanel } from './DataPanel'

export function ReviewPage({ id, readOnly, onBack }: { id: string; readOnly: boolean; onBack: () => void }) {
  const queryClient = useQueryClient()
  const workbenchRef = useRef<HTMLDivElement>(null)
  const [split, setSplit] = useState(52)
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
    if (window.matchMedia('(max-width: 920px)').matches) return
    event.preventDefault()
    const divider = event.currentTarget
    divider.setPointerCapture(event.pointerId)
    const move = (pointer: globalThis.PointerEvent) => {
      const rect = workbenchRef.current?.getBoundingClientRect()
      if (!rect) return
      setSplit(Math.max(34, Math.min(68, (pointer.clientX - rect.left) / rect.width * 100)))
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
  const selectedEvidence = selectedField?.startsWith('lines.')
    ? (() => { const [, index, property] = selectedField.split('.'); return document.lines[Number(index)]?.evidence?.[property] ?? null })()
    : selectedField ? document.fields[selectedField] ?? null : null
  return <main className="review-page">
    <div className="review-topline"><button className="text-action back-link" onClick={onBack}><ArrowLeft size={17} /> Review queue</button><span className="review-top-separator">/</span><span>{document.filename}</span><button className="icon-button review-refresh" onClick={() => detail.refetch()} title="Refresh document" aria-label="Refresh document"><RotateCcw size={16} /></button></div>
    <div className="review-header"><div className="review-title"><span className="section-kicker">DOCUMENT / {kindLabel(document.kind).toUpperCase()}</span><h1>{document.fields.number?.value || document.fields.invoice_number?.value || document.filename}</h1><div className="review-meta"><StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill><span>Version {document.version}</span><span>{document.pages.length} page{document.pages.length === 1 ? '' : 's'}</span><span>{document.findings.length} finding{document.findings.length === 1 ? '' : 's'}</span></div></div><div className="review-header-actions">{!readOnly && document.version > 0 && !['queued', 'processing', 'failed', 'cancelled'].includes(document.status) && <button className="button button-secondary" disabled={revalidate.isPending} onClick={() => revalidate.mutate()}><RotateCcw size={15} /> {revalidate.isPending ? 'Checking…' : 'Revalidate'}</button>}<div className="review-header-note"><FileText size={18} /><span>Evidence-linked<br />review record</span><ArrowUpRight size={16} /></div></div></div>
    {revalidate.isError && <div className="notice notice-red" role="alert">{displayError(revalidate.error)}</div>}
    {['queued', 'processing'].includes(document.status) && <div className="notice notice-blue"><RotateCcw size={17} /> Extraction is still running. This view will refresh as pages complete.</div>}
    {document.status === 'failed' && <div className="notice notice-red"><FileText size={17} /> Processing failed. Open Batch intake to inspect the job error and retry.</div>}
    <div className="workbench" ref={workbenchRef} style={{ '--source-width': `${split}%` } as React.CSSProperties}>
      <SourceViewer document={document} selectedField={selectedField} selectedEvidence={selectedEvidence} pageNumber={pageNumber} onPageChange={changePage} />
      <div className="panel-resizer" role="separator" tabIndex={0} aria-label="Resize source and data panels" aria-orientation="vertical" aria-valuenow={split} aria-valuemin={34} aria-valuemax={68} onPointerDown={startResize} onKeyDown={(event) => { if (event.key === 'ArrowLeft') { event.preventDefault(); setSplit((value) => Math.max(34, value - 3)) } if (event.key === 'ArrowRight') { event.preventDefault(); setSplit((value) => Math.min(68, value + 3)) } }}><Columns2 size={15} /></div>
      <DataPanel document={document} selectedField={selectedField} onSelectField={setSelectedField} onOpenMatch={(matchedId) => { window.location.hash = `/document/${encodeURIComponent(matchedId)}` }} readOnly={readOnly} onCorrect={onCorrect} correctionPending={correct.isPending} correctionError={correct.error} onDecide={onDecide} decisionPendingId={decisionPendingId} decisionError={decide.error} onDecideMatch={onDecideMatch} matchPendingId={matchPendingId} matchDecisionError={decideMatch.error} onDecideLineMatch={onDecideLineMatch} lineMatchPendingIndex={lineMatchPendingIndex} lineMatchDecisionError={decideLineMatch.error} onApprove={() => approve.mutate(document.version)} approvalPending={approve.isPending} approvalError={approve.error} onExport={onExport} exportPending={exportPending} exportError={exportError} />
    </div>
    {correct.isSuccess && <div className="sr-only" role="status">Correction saved and validation rerun.</div>}
    {approve.isSuccess && <div className="sr-only" role="status">Document version approved.</div>}
    {decide.isSuccess && <div className="sr-only" role="status">Review decision recorded.</div>}
    {decideMatch.isSuccess && <div className="sr-only" role="status">Purchase order decision recorded.</div>}
    {decideLineMatch.isSuccess && <div className="sr-only" role="status">Purchase order line mapping recorded.</div>}
    {Boolean(exportError) && <div className="sr-only" role="alert">{displayError(exportError)}</div>}
  </main>
}
