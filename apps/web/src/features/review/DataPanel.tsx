import { useState, type FormEvent } from 'react'
import { AlertTriangle, ArrowRight, Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, FileSpreadsheet, History, Pencil, ShieldCheck, X } from 'lucide-react'
import type { DocumentDetail, FieldEvidence, Finding, HistoryEvent, InvoiceLine, LineMatchGroup, MatchProposal, MatchResolution } from '../../api/types'
import { StatusPill } from '../../components/States'
import { displayError, fieldOrder, formatDate, formatMoney, labelForField, statusLabel, statusTone } from '../../lib/format'

type Tab = 'record' | 'findings' | 'history'
type EditTarget = { field: string; label: string; value: string; raw: string | null }

function EditForm({ target, pending, error, onCancel, onSubmit }: { target: EditTarget; pending: boolean; error: unknown; onCancel: () => void; onSubmit: (field: string, value: string, reason: string) => Promise<boolean> }) {
  const [value, setValue] = useState(target.value)
  const [reason, setReason] = useState('')
  const submit = async (event: FormEvent) => { event.preventDefault(); await onSubmit(target.field, value.trim(), reason.trim()) }
  return <form className="edit-form" onSubmit={submit}><div className="edit-form-title"><span className="section-kicker">CORRECT EXTRACTED VALUE</span><button type="button" className="icon-button" aria-label="Close correction form" onClick={onCancel}><X size={17} /></button></div><h3>{target.label}</h3><div className="before-after"><div><small>BEFORE</small><strong>{target.value || 'Missing'}</strong></div><ArrowRight size={17} /><div><small>AFTER</small><strong>{value || 'Missing'}</strong></div></div>{target.raw && <p className="raw-reference">Source text: <q>{target.raw}</q></p>}<label htmlFor="edit-value">Correct value</label><input id="edit-value" value={value} onChange={(event) => setValue(event.target.value)} autoFocus /><label htmlFor="edit-reason">Reason for correction <span>*</span></label><textarea id="edit-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="For example: OCR read 8 as 3 on page 2" required rows={2} />{Boolean(error) && <p className="inline-error" role="alert">{displayError(error)}</p>}<div className="edit-actions"><button type="button" className="button button-secondary" onClick={onCancel}>Cancel</button><button type="submit" className="button button-primary" disabled={pending || !reason.trim()}>{pending ? 'Saving…' : 'Save & revalidate'} <Check size={15} /></button></div></form>
}

function EvidenceBadge({ evidence }: { evidence: FieldEvidence }) {
  if (evidence.page_number == null) return <span className="evidence-badge evidence-missing"><CircleHelp size={13} /> No source link</span>
  return <span className="evidence-badge"><span className="evidence-led" /> Page {evidence.page_number}{evidence.bbox ? ' · box' : evidence.span_start != null ? ' · text' : ''}</span>
}

function FieldRow({ field, evidence, selected, canEdit, onSelect, onEdit }: { field: string; evidence: FieldEvidence; selected: boolean; canEdit: boolean; onSelect: () => void; onEdit: () => void }) {
  const value = evidence.value == null || evidence.value === '' ? 'Missing' : String(evidence.value)
  return <div className={`field-row ${selected ? 'field-selected' : ''}`}><button className="field-select" onClick={onSelect} aria-pressed={selected}><span className="field-name">{labelForField(field)}</span><span className={`field-value ${value === 'Missing' ? 'field-missing' : ''}`}>{value}</span><EvidenceBadge evidence={evidence} /></button>{canEdit && <button className="icon-button field-edit" onClick={onEdit} aria-label={`Edit ${labelForField(field)}`} title={`Edit ${labelForField(field)}`}><Pencil size={15} /></button>}</div>
}

function FindingCard({ finding, canDecide, onDecide, pendingId }: { finding: Finding; canDecide: boolean; onDecide: (finding: Finding, decision: 'accepted' | 'rejected') => void; pendingId: string | null }) {
  const details = finding.details ? Object.entries(finding.details).filter(([key]) => finding.code !== 'AMBIGUOUS_LINE_MATCH' || !['candidates', 'invoice_line_indices'].includes(key)) : []
  const open = ['open', 'pending', 'needs_review'].includes(finding.status)
  const matchDecisionRequired = finding.code === 'AMBIGUOUS_PO'
  const lineMappingRequired = finding.code === 'AMBIGUOUS_LINE_MATCH'
  return <article className={`finding-card ${finding.severity === 'error' || finding.severity === 'critical' ? 'finding-critical' : ''}`}><div className="finding-top"><span className="finding-icon"><AlertTriangle size={17} /></span><div><span className="finding-code">{finding.code.replace(/_/g, ' ')}</span><h3>{finding.message}</h3></div><StatusPill tone={statusTone(finding.status)}>{statusLabel(finding.status)}</StatusPill></div>{details.length > 0 && <div className="finding-details">{details.map(([key, value]) => <div key={key}><span>{labelForField(key)}</span><strong>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</strong></div>)}</div>}{open && matchDecisionRequired && <p className="form-hint">Select a purchase order below or explicitly reject all proposals to resolve this finding.</p>}{open && lineMappingRequired && <p className="form-hint">Correct the affected line fields to resolve this match ambiguity before approval.</p>}{open && canDecide && !matchDecisionRequired && !lineMappingRequired && <div className="finding-actions"><button className="button button-secondary" disabled={pendingId === finding.id} onClick={() => onDecide(finding, 'rejected')}><X size={14} /> Reject finding</button><button className="button button-amber" disabled={pendingId === finding.id} onClick={() => onDecide(finding, 'accepted')}><Check size={14} /> Accept finding</button></div>}{!canDecide && open && !matchDecisionRequired && !lineMappingRequired && <p className="form-hint">Viewer access cannot record a review decision.</p>}</article>
}

function HistoryView({ history }: { history: HistoryEvent[] }) {
  if (!history.length) return <div className="clear-findings"><Clock3 size={27} /><h3>No changes yet</h3><p>Edits and decisions will appear after the first review action.</p></div>
  const asMap = (value: HistoryEvent['before']): Record<string, unknown> => value && typeof value === 'object' ? value : {}
  return <div className="timeline">{history.map((event, index) => {
    const before = asMap(event.before)
    const after = asMap(event.after)
    const key = event.field || Object.keys(after)[0] || Object.keys(before)[0]
    return <div key={event.id || index} className="timeline-item"><span className="timeline-dot"><History size={14} /></span><div><strong>{String(event.action || event.event || 'Document updated').replace(/_/g, ' ')}</strong><p>{key && <>{labelForField(key)}: <del>{String(before[key] ?? 'Missing')}</del> <ChevronRight size={12} /> <ins>{String(after[key] ?? 'Missing')}</ins></>}{event.note && <span>{event.note}</span>}</p><small>{formatDate(event.created_at || event.timestamp)} · Version updated</small></div></div>
  })}</div>
}

function LineItems({ lines, currency, canMutate, selectedField, onSelectField, onEdit }: { lines: InvoiceLine[]; currency: string | null; canMutate: boolean; selectedField: string | null; onSelectField: (field: string) => void; onEdit: (target: EditTarget) => void }) {
  const valueButton = (index: number, property: 'quantity' | 'unit_price' | 'amount', display: string) => {
    const key = `lines.${index}.${property}`
    const evidence = lines[index].evidence?.[property]
    return <button className={`line-evidence-button ${selectedField === key ? 'line-evidence-active' : ''}`} onClick={() => onSelectField(key)} title={evidence?.page_number ? `Show page ${evidence.page_number} evidence` : 'No source coordinates available'} aria-label={`Show evidence for line ${index + 1} ${property.replace('_', ' ')}`}>
      {display}<small>{evidence?.page_number ? `p.${evidence.page_number}` : '—'}</small>
    </button>
  }
  if (!lines.length) return <p className="muted">No line items were extracted.</p>
  return <div className="line-table-wrap"><table className="line-table"><thead><tr><th>Item / description</th><th>Qty</th><th>Unit</th><th>Price</th><th>Amount</th>{canMutate && <th><span className="sr-only">Edit</span></th>}</tr></thead><tbody>{lines.map((line, index) => <tr key={line.id || index}><td><strong>{line.sku || `Item ${index + 1}`}</strong><small>{line.description || 'No description'}</small></td><td>{valueButton(index, 'quantity', String(line.quantity ?? '—'))}</td><td>{line.unit || '—'}</td><td>{valueButton(index, 'unit_price', formatMoney(line.unit_price, currency))}</td><td>{valueButton(index, 'amount', formatMoney(line.amount, currency))}</td>{canMutate && <td><div className="line-edit-menu"><button className="icon-button" aria-label={`Edit line ${index + 1} unit price`} title="Edit unit price" onClick={() => onEdit({ field: `lines.${index}.unit_price`, label: `Line ${index + 1} unit price`, value: String(line.unit_price ?? ''), raw: line.evidence?.unit_price?.raw ?? null })}><Pencil size={14} /></button><button className="icon-button" aria-label={`Edit line ${index + 1} quantity`} title="Edit quantity" onClick={() => onEdit({ field: `lines.${index}.quantity`, label: `Line ${index + 1} quantity`, value: String(line.quantity ?? ''), raw: line.evidence?.quantity?.raw ?? null })}><span className="small-q">Q</span></button></div></td>}</tr>)}</tbody></table></div>
}

function MatchList({ matches, resolution, needsResolution, canDecide, readOnly, onOpen, onDecide, pendingId, error }: { matches: MatchProposal[]; resolution: MatchResolution | null; needsResolution: boolean; canDecide: boolean; readOnly: boolean; onOpen: (id: string) => void; onDecide: (decision: 'selected' | 'rejected', poId: string | null, note: string) => void; pendingId: string | null; error: unknown }) {
  const [note, setNote] = useState('')
  if (!matches.length && !needsResolution && !resolution) return null
  const canAct = canDecide && (needsResolution || Boolean(resolution))
  const selected = matches.find((match) => match.po_id === resolution?.po_id)
  return <section className="match-section" aria-label="Purchase order proposals">
    <span className="section-kicker">PURCHASE ORDER MATCHES</span>
    <h3>{needsResolution ? 'Choose the matching PO' : 'Purchase order decision'}</h3>
    <p className="match-intro">Inspect the proposed source before deciding. This decision is recorded against version {resolution?.version ?? 'the current document'}.</p>
    {resolution && <div className="match-resolution" role="status"><CheckCircle2 size={16} /><span>{resolution.decision === 'selected' ? `Selected ${selected?.po_number || 'purchase order'}` : 'All PO proposals rejected'}{resolution.note ? ` · ${resolution.note}` : ''}</span></div>}
    {matches.map((match) => <article key={match.po_id} data-po-id={match.po_id} className={`match-candidate ${match.status === 'selected' ? 'match-candidate-selected' : ''}`}>
      <div className="match-candidate-main"><strong>{match.po_number || 'Purchase order'}</strong><small>Proposal score {Math.round(match.score * 100)}% · Source {match.document_id?.slice(0, 8) || match.po_id.slice(0, 8)}</small></div>
      <StatusPill tone={match.status === 'selected' || match.status === 'matched' ? 'green' : match.status === 'proposed' ? 'amber' : 'neutral'}>{statusLabel(match.status)}</StatusPill>
      <div className="match-candidate-actions">{match.document_id && <button className="text-action" aria-label={`Inspect PO source ${match.document_id.slice(0, 8)}`} onClick={() => onOpen(match.document_id!)}>Inspect PO <ArrowRight size={14} /></button>}{canAct && match.status !== 'selected' && <button className="button button-secondary" aria-label={`Select PO source ${(match.document_id || match.po_id).slice(0, 8)}`} disabled={Boolean(pendingId)} onClick={() => onDecide('selected', match.po_id, note.trim())}>{pendingId === match.po_id ? 'Saving…' : 'Select this PO'}</button>}</div>
    </article>)}
    {canAct && <div className="match-decision-actions"><label htmlFor="match-decision-note">Decision note <span>(optional)</span></label><textarea id="match-decision-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={2} placeholder="Record why this PO was selected or rejected" /><button className="button button-secondary" disabled={Boolean(pendingId) || resolution?.decision === 'rejected'} onClick={() => onDecide('rejected', null, note.trim())}>{pendingId === 'reject-all' ? 'Saving…' : resolution?.decision === 'rejected' ? 'All proposals rejected' : 'Reject all proposals'}</button></div>}
    {readOnly && needsResolution && <p className="form-hint">Viewer access can inspect proposals. An operator must record the decision.</p>}
    {Boolean(error) && <p className="inline-error" role="alert">{displayError(error)}</p>}
  </section>
}

function LineMappingList({ groups, lines, mappings, currency, canDecide, readOnly, onMap, pendingIndex, error }: { groups: LineMatchGroup[]; lines: InvoiceLine[]; mappings: Record<string, string>; currency: string | null; canDecide: boolean; readOnly: boolean; onMap: (index: number, poLineId: string, note: string) => void; pendingIndex: number | null; error: unknown }) {
  const [note, setNote] = useState('')
  if (!groups.length && !Object.keys(mappings).length) return null
  return <section className="line-map-section" aria-label="Purchase order line mapping">
    <span className="section-kicker">LINE MATCHING</span>
    <h3>Map invoice lines to PO lines</h3>
    <p className="match-intro">Choose the specific ordered line for each ambiguous invoice line. Every choice creates a new review version.</p>
    {groups.map((group) => {
      const invoiceLine = lines[group.invoice_line_index]
      const selectedId = mappings[String(group.invoice_line_index)]
      return <article className="line-map-group" key={group.invoice_line_index}>
        <div className="line-map-header"><div><strong>Invoice line {group.invoice_line_index + 1} · {group.sku}</strong><small>{invoiceLine?.description || 'No description'} · Qty {invoiceLine?.quantity ?? '—'} · {formatMoney(invoiceLine?.unit_price, currency)} each</small></div><StatusPill tone={selectedId ? 'green' : 'amber'}>{selectedId ? 'Mapped' : 'Needs mapping'}</StatusPill></div>
        <div className="line-map-options">{group.candidates.map((candidate) => <div className={`line-map-option ${selectedId === candidate.po_line_id ? 'line-map-option-selected' : ''}`} key={candidate.po_line_id}><div><strong>{candidate.description || group.sku}</strong><small>PO qty {candidate.quantity ?? '—'} · {formatMoney(candidate.unit_price, currency)} each</small></div>{selectedId === candidate.po_line_id ? <StatusPill tone="green">Selected</StatusPill> : canDecide && <button className="button button-secondary" aria-label={`Map invoice line ${group.invoice_line_index + 1} to PO line ${candidate.po_line_id.slice(0, 8)} at ${formatMoney(candidate.unit_price, currency)}`} disabled={pendingIndex !== null} onClick={() => onMap(group.invoice_line_index, candidate.po_line_id, note.trim())}>{pendingIndex === group.invoice_line_index ? 'Saving…' : 'Map to this line'}</button>}</div>)}</div>
      </article>
    })}
    {canDecide && <div className="match-decision-actions"><label htmlFor="line-match-note">Mapping note <span>(optional)</span></label><textarea id="line-match-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={2} placeholder="Record the reason for this line mapping" /></div>}
    {readOnly && groups.some((group) => !mappings[String(group.invoice_line_index)]) && <p className="form-hint">Viewer access can inspect candidates. An operator must map these lines.</p>}
    {Boolean(error) && <p className="inline-error" role="alert">{displayError(error)}</p>}
  </section>
}

export function DataPanel({ document, selectedField, onSelectField, onOpenMatch, readOnly, onCorrect, correctionPending, correctionError, onDecide, decisionPendingId, decisionError, onDecideMatch, matchPendingId, matchDecisionError, onDecideLineMatch, lineMatchPendingIndex, lineMatchDecisionError, onApprove, approvalPending, approvalError, onExport, exportPending, exportError }: {
  document: DocumentDetail; selectedField: string | null; onSelectField: (field: string) => void; onOpenMatch: (id: string) => void; readOnly: boolean
  onCorrect: (field: string, value: string, reason: string) => Promise<boolean>; correctionPending: boolean; correctionError: unknown
  onDecide: (finding: Finding, decision: 'accepted' | 'rejected') => void; decisionPendingId: string | null; decisionError: unknown
  onDecideMatch: (decision: 'selected' | 'rejected', poId: string | null, note: string) => void; matchPendingId: string | null; matchDecisionError: unknown
  onDecideLineMatch: (index: number, poLineId: string, note: string) => void; lineMatchPendingIndex: number | null; lineMatchDecisionError: unknown
  onApprove: () => void; approvalPending: boolean; approvalError: unknown
  onExport: (format: 'csv' | 'xlsx' | 'json') => void; exportPending: string | null; exportError: unknown
}) {
  const [tab, setTab] = useState<Tab>('record')
  const [edit, setEdit] = useState<EditTarget | null>(null)
  const fields = Object.entries(document.fields).sort(([a], [b]) => (fieldOrder.indexOf(a) < 0 ? 1000 : fieldOrder.indexOf(a)) - (fieldOrder.indexOf(b) < 0 ? 1000 : fieldOrder.indexOf(b)))
  const approvalCurrent = document.approval && (document.approval.version == null || document.approval.version === document.version)
  const openFindings = document.findings.filter((finding) => ['open', 'pending', 'needs_review'].includes(finding.status))
  const canMutate = !readOnly && !['queued', 'processing', 'failed', 'cancelled'].includes(document.status)
  const blockingFindings = openFindings.filter((finding) => ['error', 'critical'].includes(finding.severity) || ['AMBIGUOUS_PO', 'AMBIGUOUS_LINE_MATCH'].includes(finding.code))
  const poAmbiguous = openFindings.some((finding) => finding.code === 'AMBIGUOUS_PO')
  return <section className="data-panel" aria-label="Structured data and review">
    <div className="panel-heading"><div><span className="section-kicker">STRUCTURED RECORD</span><h2>Version {document.version} <StatusPill tone={statusTone(document.status)}>{statusLabel(document.status)}</StatusPill></h2></div></div>
    <div className="data-tabs" role="tablist" aria-label="Record detail"><button role="tab" aria-selected={tab === 'record'} className={tab === 'record' ? 'tab-active' : ''} onClick={() => setTab('record')}>Extracted data</button><button role="tab" aria-selected={tab === 'findings'} className={tab === 'findings' ? 'tab-active' : ''} onClick={() => setTab('findings')}>Findings <b>{openFindings.length}</b></button><button role="tab" aria-selected={tab === 'history'} className={tab === 'history' ? 'tab-active' : ''} onClick={() => setTab('history')}>History</button></div>
    <div className="data-scroll">
      {tab === 'record' && <div className="record-content">{edit ? <EditForm key={edit.field} target={edit} pending={correctionPending} error={correctionError} onCancel={() => setEdit(null)} onSubmit={async (field, value, reason) => { const saved = await onCorrect(field, value, reason); if (saved) setEdit(null); return saved }} /> : <><div className="record-note"><ScanIcon /><span>Select any field to inspect its evidence on the source page.</span></div><div className="field-section"><div className="subsection-heading"><h3>Document details</h3><span>{fields.length} fields</span></div>{fields.map(([field, evidence]) => <FieldRow key={field} field={field} evidence={evidence} selected={selectedField === field} canEdit={canMutate} onSelect={() => onSelectField(field)} onEdit={() => setEdit({ field, label: labelForField(field), value: String(evidence.value ?? ''), raw: evidence.raw })} />)}</div>
        <div className="field-section line-section"><div className="subsection-heading"><h3>Line items</h3><span>{document.lines.length} items</span></div><LineItems lines={document.lines} currency={document.fields.currency?.value?.toString() ?? null} canMutate={canMutate} selectedField={selectedField} onSelectField={onSelectField} onEdit={setEdit} /></div>
        <div className="formula-card"><span className="section-kicker">RECONCILIATION</span><div><span>Subtotal</span><strong>{formatMoney(document.fields.subtotal?.value, document.fields.currency?.value?.toString())}</strong></div><div><span>+ Tax</span><strong>{formatMoney(document.fields.tax?.value, document.fields.currency?.value?.toString())}</strong></div><div><span>+ Freight</span><strong>{formatMoney(document.fields.freight?.value, document.fields.currency?.value?.toString())}</strong></div><div><span>− Discounts</span><strong>{formatMoney(document.fields.discounts?.value ?? document.fields.discount?.value, document.fields.currency?.value?.toString())}</strong></div><div className="formula-total"><span>Stated total</span><strong>{formatMoney(document.fields.total?.value, document.fields.currency?.value?.toString())}</strong></div><small>Arithmetic checks and currency rounding are calculated on the server.</small></div>
      </>}</div>}
      {tab === 'findings' && <div className="findings-content"><div className="findings-intro"><h3>{openFindings.length} open finding{openFindings.length === 1 ? '' : 's'}</h3><p>Decisions are recorded against this document version. Correcting a value reruns validation.</p></div>{Boolean(decisionError) && <p className="inline-error" role="alert">{displayError(decisionError)}</p>}{document.findings.length ? document.findings.map((finding) => <FindingCard key={finding.id} finding={finding} canDecide={canMutate} onDecide={onDecide} pendingId={decisionPendingId} />) : <div className="clear-findings"><CheckCircle2 size={29} /><h3>No findings generated</h3><p>Review the extracted fields and source evidence before approval.</p></div>}<MatchList matches={document.matches} resolution={document.match_resolution} needsResolution={poAmbiguous} canDecide={canMutate} readOnly={readOnly} onOpen={onOpenMatch} onDecide={onDecideMatch} pendingId={matchPendingId} error={matchDecisionError} /><LineMappingList groups={document.line_match_candidates || []} lines={document.lines} mappings={document.line_matches || {}} currency={document.fields.currency?.value ?? null} canDecide={canMutate} readOnly={readOnly} onMap={onDecideLineMatch} pendingIndex={lineMatchPendingIndex} error={lineMatchDecisionError} /></div>}
      {tab === 'history' && <div className="history-content"><div className="findings-intro"><h3>Version history</h3><p>Corrections, review decisions, and approvals are recorded here.</p></div><HistoryView history={document.history} /></div>}
    </div>
    <div className="data-footer">{approvalCurrent ? <div className="approval-confirmed"><ShieldCheck size={18} /><span>Version {document.version} approved</span></div> : <div className="approval-context"><strong>{blockingFindings.length ? 'Review required before approval' : 'Ready to approve?'}</strong><small>{blockingFindings.length ? `${blockingFindings.length} blocking finding${blockingFindings.length === 1 ? '' : 's'} must be resolved` : openFindings.length ? `${openFindings.length} nonblocking finding${openFindings.length === 1 ? '' : 's'} still open` : 'Review evidence and finalize this version'}</small></div>}
      {Boolean(approvalError) && <p className="inline-error" role="alert">{displayError(approvalError)}</p>}{Boolean(exportError) && <p className="inline-error" role="alert">{displayError(exportError)}</p>}
      <div className="footer-actions">{approvalCurrent ? <div className="export-actions"><button className="button button-secondary" disabled={Boolean(exportPending)} onClick={() => onExport('csv')}><FileSpreadsheet size={15} /> CSV</button><button className="button button-primary" disabled={Boolean(exportPending)} onClick={() => onExport('xlsx')}><FileSpreadsheet size={16} /> {exportPending === 'xlsx' ? 'Preparing…' : 'Download XLSX'}</button><button className="button button-secondary" disabled={Boolean(exportPending)} onClick={() => onExport('json')}>JSON</button></div> : <button className="button button-primary" disabled={!canMutate || approvalPending || blockingFindings.length > 0} title={!canMutate ? readOnly ? 'Viewer access cannot approve' : 'Document processing is not complete' : blockingFindings.length ? 'Resolve blocking findings before approval' : undefined} onClick={onApprove}><ShieldCheck size={17} /> {approvalPending ? 'Approving…' : 'Approve version'} <ArrowRight size={16} /></button>}</div>
    </div>
  </section>
}

function ScanIcon() { return <span className="record-note-icon"><CircleHelp size={16} /></span> }
