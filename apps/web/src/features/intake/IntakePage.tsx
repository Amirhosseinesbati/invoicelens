import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ArrowRight, Check, FileImage, FileText, LoaderCircle, RotateCcw, Upload, X } from 'lucide-react'
import { api } from '../../api/client'
import type { Job, UploadItem } from '../../api/types'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../../components/States'
import { displayError, formatDate, statusLabel, statusTone } from '../../lib/format'

import { prepareSelection } from '../../lib/intake'

function percentage(job: Job): number {
  const value = job.progress <= 1 && !['complete', 'completed'].includes(job.status) ? job.progress * 100 : job.progress
  return Math.min(100, Math.max(0, Math.round(value)))
}

function JobRow({ job, readOnly, onOpen }: { job: Job; readOnly: boolean; onOpen: (id: string) => void }) {
  const queryClient = useQueryClient()
  const cancel = useMutation({ mutationFn: () => api.cancelJob(job.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }) })
  const retry = useMutation({ mutationFn: () => api.retryJob(job.id), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }) })
  const active = ['queued', 'running', 'processing'].includes(job.status)
  return <div className="job-row"><span className="job-icon">{active ? <LoaderCircle size={19} className="spin" /> : ['complete', 'completed'].includes(job.status) ? <Check size={19} /> : <AlertCircle size={19} />}</span><div className="job-main"><div><strong>Document {job.document_id ? job.document_id.slice(0, 8) : job.id.slice(0, 8)}</strong><StatusPill tone={statusTone(job.status)}>{statusLabel(job.status)}</StatusPill></div><small>{active ? `Page ${job.current_page} of ${job.total_pages || '—'}` : job.error || `Updated ${formatDate(job.updated_at)}`}</small><div className="progress-track" role="progressbar" aria-valuenow={percentage(job)} aria-valuemin={0} aria-valuemax={100} aria-label={`Job ${job.id} progress`}><span style={{ width: `${percentage(job)}%` }} /></div></div><span className="job-percent">{percentage(job)}%</span><div className="job-actions">{job.document_id && <button className="text-action" onClick={() => onOpen(job.document_id!)}>Open <ArrowRight size={15} /></button>}{active && !readOnly && <button className="icon-button" onClick={() => cancel.mutate()} disabled={cancel.isPending} aria-label={`Cancel job ${job.id}`} title="Cancel job"><X size={16} /></button>}{['failed', 'cancelled'].includes(job.status) && !readOnly && <button className="icon-button" onClick={() => retry.mutate()} disabled={retry.isPending} aria-label={`Retry job ${job.id}`} title="Retry job"><RotateCcw size={16} /></button>}</div>{(cancel.isError || retry.isError) && <p className="inline-error job-error" role="alert">{displayError(cancel.error || retry.error)}</p>}</div>
}

function UploadResults({ items, onOpen }: { items: UploadItem[]; onOpen: (id: string) => void }) {
  return <div className="upload-results" role="status"><strong>{items.some((item) => item.document_id) ? 'Batch received' : 'Files need attention'}</strong>{items.map((item, index) => <div key={`${item.document_id}-${index}`}><StatusPill tone={item.status === 'rejected' ? 'red' : statusTone(item.status)}>{item.deduplicated ? 'Already in workspace' : statusLabel(item.status)}</StatusPill><span>{item.filename || item.document_id || `File ${index + 1}`}</span>{item.error && <small>{item.error}</small>}{item.document_id && <button className="text-action" onClick={() => onOpen(item.document_id!)}>Open <ArrowRight size={14} /></button>}</div>)}</div>
}

export function IntakePage({ readOnly, onOpenDocument }: { readOnly: boolean; onOpenDocument: (id: string) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [results, setResults] = useState<UploadItem[] | null>(null)
  const [dragged, setDragged] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.jobs, refetchInterval: 3_000 })
  const upload = useMutation({ mutationFn: () => api.upload(files), onSuccess: (response) => { setResults(response.items); setFiles([]); queryClient.invalidateQueries({ queryKey: ['jobs'] }); queryClient.invalidateQueries({ queryKey: ['documents'] }); queryClient.invalidateQueries({ queryKey: ['overview'] }) } })
  useEffect(() => {
    const active = (jobs.data ?? []).filter((job) => ['queued', 'running', 'processing'].includes(job.status)).slice(0, 8)
    const streams = active.map((job) => {
      const source = new EventSource(`/api/jobs/${encodeURIComponent(job.id)}/events`, { withCredentials: true })
      const update = () => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); queryClient.invalidateQueries({ queryKey: ['documents'] }); queryClient.invalidateQueries({ queryKey: ['overview'] }) }
      source.onmessage = update
      source.addEventListener('progress', update)
      source.addEventListener('completed', update)
      source.addEventListener('failed', update)
      source.onerror = () => source.close()
      return source
    })
    return () => streams.forEach((stream) => stream.close())
  }, [jobs.data, queryClient])
  const addFiles = (incoming: FileList | File[]) => {
    if (upload.isPending) return
    setFileError(null); setResults(null); upload.reset()
    try { setFiles(prepareSelection(files, Array.from(incoming))) }
    catch (failure) { setFileError(displayError(failure)) }
  }
  const onDrop = (event: DragEvent) => { event.preventDefault(); setDragged(false); if (!readOnly && !upload.isPending) addFiles(event.dataTransfer.files) }
  return <main className="page intake-page"><div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> DOCUMENT INTAKE</span><h1>Batch intake</h1><p>Upload invoices, credit notes, and purchase orders. Each page is tracked through processing.</p></div><div className="intake-stat"><span>SUPPORTED FORMATS</span><strong>PDF · PNG · JPG</strong><small>Up to 20 MB per file · 30 files per batch</small></div></div>
    <div className="intake-grid"><section className="surface upload-surface"><div className="section-heading"><div><span className="section-kicker">01 / ADD DOCUMENTS</span><h2>New batch</h2></div></div><div className={`dropzone ${dragged ? 'dragged' : ''} ${readOnly ? 'drop-disabled' : ''}`} onDragOver={(event) => { event.preventDefault(); if (!readOnly) setDragged(true) }} onDragLeave={() => setDragged(false)} onDrop={onDrop}>
      <span className="drop-icon"><Upload size={25} /></span><strong>Drop files here, or browse</strong><p>Scanned and native-text files are supported. Duplicates are checked by the server.</p><button className="button button-secondary" type="button" disabled={readOnly || upload.isPending} title={readOnly ? 'Viewer access cannot upload documents' : undefined} onClick={() => inputRef.current?.click()}>Choose files</button><input ref={inputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" className="sr-only" onChange={(event) => { if (event.target.files) addFiles(event.target.files); event.target.value = '' }} /></div>
      {readOnly && <p className="form-hint">Viewer access is read only. Ask an operator to upload documents.</p>}
      {fileError && <p className="inline-error" role="alert">{fileError}</p>}
      {files.length > 0 && <div className="selected-files"><div className="selected-head"><strong>{files.length} file{files.length === 1 ? '' : 's'} ready</strong><button className="text-action" disabled={upload.isPending} onClick={() => setFiles([])}>Clear all</button></div>{files.map((file, index) => <div className="selected-file" key={`${file.name}-${index}`}><span>{file.type === 'application/pdf' ? <FileText size={17} /> : <FileImage size={17} />}</span><strong title={file.name}>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(1)} MB</small><button className="icon-button" aria-label={`Remove ${file.name}`} disabled={upload.isPending} onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))}><X size={15} /></button></div>)}<button className="button button-primary upload-submit" disabled={upload.isPending || readOnly} onClick={() => upload.mutate()}>{upload.isPending ? 'Submitting batch…' : 'Start processing'} <ArrowRight size={17} /></button></div>}
      {upload.isError && <div className="inline-error" role="alert">{displayError(upload.error)}</div>}
      {results && <UploadResults items={results} onOpen={onOpenDocument} />}
    </section><aside className="intake-aside"><span className="section-kicker">THE INTAKE PATH</span><div className="path-step"><b>01</b><div><strong>Source retained</strong><p>The original file stays scoped to this workspace for review.</p></div></div><div className="path-step"><b>02</b><div><strong>Page by page</strong><p>Text extraction or OCR runs before structured extraction and validation.</p></div></div><div className="path-step"><b>03</b><div><strong>Exceptions surfaced</strong><p>Uncertain evidence and rule discrepancies go to the review queue.</p></div></div></aside></div>
    <section className="surface jobs-surface"><div className="section-heading"><div><span className="section-kicker">02 / PROCESSING</span><h2>Batch activity</h2></div><button className="text-action" onClick={() => jobs.refetch()}><RotateCcw size={15} /> Refresh</button></div>{jobs.isPending ? <LoadingState label="Loading jobs…" /> : jobs.isError ? <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} compact /> : jobs.data.length ? <div className="job-list">{[...jobs.data].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((job) => <JobRow key={job.id} job={job} readOnly={readOnly} onOpen={onOpenDocument} />)}</div> : <EmptyState title="No batches in progress" description="Submitted documents and page-level progress will appear here." />}</section>
  </main>
}
