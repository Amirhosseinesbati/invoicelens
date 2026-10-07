import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Download, Maximize2, Minus, Plus, ScanSearch } from 'lucide-react'
import { api } from '../../api/client'
import type { DocumentDetail, FieldEvidence, Page } from '../../api/types'
import { EmptyState, ErrorState, LoadingState } from '../../components/States'
import { displayError, downloadBlob, labelForField } from '../../lib/format'

function useBlobUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!blob) { setUrl(null); return }
    const next = URL.createObjectURL(blob)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [blob])
  return url
}

function PageThumb({ documentId, page, active, onSelect }: { documentId: string; page: Page; active: boolean; onSelect: () => void }) {
  const image = useQuery({ queryKey: ['page-image', documentId, page.page_number], queryFn: () => api.pageImage(documentId, page.page_number), staleTime: Infinity })
  const url = useBlobUrl(image.data)
  return <button className={`page-thumb ${active ? 'page-thumb-active' : ''}`} onClick={onSelect} aria-label={`View page ${page.page_number}`} aria-current={active ? 'page' : undefined}><span className="thumb-image">{url ? <img src={url} alt="" /> : <span>{page.page_number}</span>}</span><small>PAGE {String(page.page_number).padStart(2, '0')}</small></button>
}

function EvidenceText({ page, evidence }: { page: Page; evidence: FieldEvidence | null }) {
  const text = page.text || ''
  if (!text) return <p className="muted">No searchable text is available for this page.</p>
  if (!evidence || evidence.page_number !== page.page_number || evidence.span_start == null || evidence.span_end == null || evidence.span_start < 0 || evidence.span_end > text.length || evidence.span_end <= evidence.span_start) return <pre>{text}</pre>
  return <pre>{text.slice(0, evidence.span_start)}<mark>{text.slice(evidence.span_start, evidence.span_end)}</mark>{text.slice(evidence.span_end)}</pre>
}

export function SourceViewer({ document, selectedField, selectedEvidence, pageNumber, onPageChange }: { document: DocumentDetail; selectedField: string | null; selectedEvidence: FieldEvidence | null; pageNumber: number; onPageChange: (page: number) => void }) {
  const [zoom, setZoom] = useState(100)
  const [fitWidth, setFitWidth] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showText, setShowText] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const page = document.pages.find((item) => item.page_number === pageNumber) ?? document.pages[0]
  const pageImage = useQuery({ queryKey: ['page-image', document.id, page?.page_number], queryFn: () => api.pageImage(document.id, page!.page_number), enabled: Boolean(page), staleTime: Infinity })
  const imageUrl = useBlobUrl(pageImage.data)
  useEffect(() => {
    const element = scrollRef.current
    if (!element || !page) return
    const fit = () => {
      const style = getComputedStyle(element)
      const width = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
      const height = element.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)
      const ratio = page.width > 0 && page.height > 0 ? page.width / page.height : 0.772
      if (width > 0 && height > 0) setFitWidth(Math.min(width, height * ratio))
    }
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(element)
    return () => observer.disconnect()
  }, [page])

  useEffect(() => {
    if (selectedEvidence?.page_number && selectedEvidence.page_number !== pageNumber) onPageChange(selectedEvidence.page_number)
  }, [selectedEvidence?.page_number, pageNumber, onPageChange])
  const downloadSource = async () => {
    setDownloadError(null)
    try { downloadBlob(await api.source(document.id), document.filename) } catch (error) { setDownloadError(displayError(error)) }
  }
  const keyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowLeft' && pageNumber > 1) { event.preventDefault(); onPageChange(pageNumber - 1) }
    if (event.key === 'ArrowRight' && pageNumber < document.pages.length) { event.preventDefault(); onPageChange(pageNumber + 1) }
    if (event.key === '+' || event.key === '=') { event.preventDefault(); setZoom((value) => Math.min(180, value + 20)) }
    if (event.key === '-') { event.preventDefault(); setZoom((value) => Math.max(60, value - 20)) }
  }
  if (!page) return <section className="source-panel" aria-label="Source document"><div className="panel-heading"><div><h2><span className="source-file-icon" aria-hidden="true"><ScanSearch size={16} /></span>{document.filename}</h2></div></div><EmptyState title="Pages are not available yet" description="The source viewer will be ready when intake finishes processing the file." /></section>
  const bbox = selectedEvidence?.bbox && selectedEvidence.page_number === page?.page_number ? selectedEvidence.bbox : null
  return <section className="source-panel" aria-label="Source document">

    {downloadError && <p className="inline-error" role="alert">{downloadError}</p>}
    <div className="source-toolbar"><h2 className="source-toolbar-filename">{document.filename}</h2><span className="page-indicator">Page <strong>{page?.page_number ?? 0}</strong> / {document.pages.length}</span><div className="toolbar-divider" /><button className="icon-button" onClick={() => onPageChange(Math.max(1, pageNumber - 1))} disabled={pageNumber <= 1} aria-label="Previous page"><ChevronLeft size={17} /></button><button className="icon-button" onClick={() => onPageChange(Math.min(document.pages.length, pageNumber + 1))} disabled={pageNumber >= document.pages.length} aria-label="Next page"><ChevronRight size={17} /></button><div className="toolbar-spacer" /><button className="icon-button" onClick={() => setZoom((value) => Math.max(60, value - 20))} disabled={zoom <= 60} aria-label="Zoom out"><Minus size={16} /></button><span className="zoom-value">{zoom}%</span><button className="icon-button" onClick={() => setZoom((value) => Math.min(180, value + 20))} disabled={zoom >= 180} aria-label="Zoom in"><Plus size={16} /></button><button className="icon-button" onClick={() => setZoom(100)} aria-label="Reset zoom" title="Reset zoom"><Maximize2 size={15} /></button><button className="icon-button" title="Download original source" aria-label="Download original source" onClick={downloadSource}><Download size={16} /></button></div>
    <div className="viewer-body"><div className={`thumbnail-rail ${document.pages.length === 1 ? 'single-page-rail' : ''}`} aria-label="Page thumbnails">{document.pages.map((item) => <PageThumb key={item.page_number} documentId={document.id} page={item} active={item.page_number === pageNumber} onSelect={() => onPageChange(item.page_number)} />)}</div><div className="source-scroll" ref={scrollRef} tabIndex={0} onKeyDown={keyDown} aria-label="Source page. Use left and right arrows to change page and plus or minus to zoom.">{pageImage.isPending ? <LoadingState label="Rendering source page…" /> : pageImage.isError ? <ErrorState error={pageImage.error} onRetry={() => pageImage.refetch()} compact /> : <div className="source-canvas" style={{ width: fitWidth ? fitWidth * zoom / 100 : `${zoom}%` }}><div className="source-image-frame">{imageUrl && <img src={imageUrl} alt={`Source page ${page?.page_number}`} />}{bbox && page && page.width > 0 && page.height > 0 && <div className="evidence-box" style={{ left: `${Math.max(0, bbox[0] / page.width * 100)}%`, top: `${Math.max(0, bbox[1] / page.height * 100)}%`, width: `${Math.min(100, (bbox[2] - bbox[0]) / page.width * 100)}%`, height: `${Math.min(100, (bbox[3] - bbox[1]) / page.height * 100)}%` }} title={`Evidence for ${selectedField}`} />}</div></div>}</div></div>
    <div className="source-evidence-dock">
      <span className="evidence-dock-icon"><ScanSearch size={17} /></span>
      <div><strong>{selectedField ? selectedField.startsWith('lines.') ? `Line ${Number(selectedField.split('.')[1]) + 1} · ${labelForField(selectedField.split('.')[2])}` : labelForField(selectedField) : 'Source evidence'}</strong><span>{selectedEvidence?.page_number === pageNumber ? bbox ? `Page ${pageNumber} · Coordinates from extraction` : selectedEvidence.span_start != null ? `Page ${pageNumber} · Text span available` : `Page ${pageNumber} · Page reference only` : 'Select a value in the review record'}</span></div>
      {selectedEvidence && <strong className="evidence-dock-value">{selectedEvidence.value || 'Missing'}</strong>}
      <button className="icon-button" onClick={() => setShowText((value) => !value)} aria-expanded={showText} aria-label={showText ? 'Hide extracted text' : 'Show extracted text'} title={showText ? 'Hide extracted text' : 'Show extracted text'}><ScanSearch size={16} /></button>
    </div>
    {showText && page && <div className="source-text"><EvidenceText page={page} evidence={selectedEvidence} /></div>}
  </section>
}
