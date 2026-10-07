import { useRef, useState, type FormEvent } from 'react'
import { Check, Download, Palette, RotateCcw, ScanLine, Upload } from 'lucide-react'
import { ThemeControl } from '../../components/ThemeControl'
import { useWorkspace } from '../../components/WorkspaceProvider'
import { accents, parseProfile, type WorkspaceProfile } from '../../lib/workspace-profile'
import { displayError, downloadBlob } from '../../lib/format'

export function WorkspaceAppearance() {
  const { profile, defaults, workspaceName, save, reset, storageError } = useWorkspace()
  const [draft, setDraft] = useState<WorkspaceProfile>(profile)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const change = <K extends keyof WorkspaceProfile>(key: K, value: WorkspaceProfile[K]) => { setDraft((previous) => ({ ...previous, [key]: value })); setMessage(null); setError(null) }
  const apply = (event: FormEvent) => {
    event.preventDefault(); setError(null)
    try { const persisted = save(parseProfile(draft)); setMessage(persisted ? 'Profile saved for this workspace in this browser.' : 'Appearance applied for this session. Export the profile to keep it.'); setDraft(parseProfile(draft)) }
    catch (failure) { setError(displayError(failure)) }
  }
  const importProfile = async (file: File | undefined) => {
    if (!file) return
    setMessage(null); setError(null)
    try {
      if (file.size > 16_384) throw new Error('Profiles must be smaller than 16 KB. Choose a profile JSON file, not an invoice.')
      setDraft(parseProfile(JSON.parse(await file.text())))
      setMessage('Profile loaded into the form. Apply changes to use it.')
    } catch (failure) { setError(failure instanceof SyntaxError ? 'This file is not valid JSON. Your saved profile is unchanged.' : displayError(failure)) }
  }
  return <section className="surface appearance-surface" aria-label="Workspace appearance">
    <div className="section-heading"><div><span className="section-kicker">MAKE IT YOUR WORKSPACE</span><h2>Appearance & preferences</h2></div><Palette size={22} /></div>
    <ThemeControl detailed /><div className="appearance-layout"><form className="appearance-form" onSubmit={apply}>
      <p className="appearance-intro">A reusable front desk for your team. Changes apply to this browser and workspace.</p>
      <div className="appearance-fields"><label>Product name<input value={draft.productName} maxLength={32} required onChange={(event) => change('productName', event.target.value)} /></label><label>Workspace display name<input aria-label="Workspace display name" aria-describedby="workspace-name-help" placeholder={workspaceName} value={draft.workspaceLabel} maxLength={64} onChange={(event) => change('workspaceLabel', event.target.value)} /><small id="workspace-name-help">Leave blank to use the server workspace name.</small></label></div>
      <fieldset className="accent-options"><legend>Accent color</legend>{accents.map((accent) => <label key={accent} className={`accent-option accent-${accent} ${draft.accent === accent ? 'accent-selected' : ''}`}><input type="radio" name="accent" value={accent} checked={draft.accent === accent} onChange={() => change('accent', accent)} /><span className="accent-swatch" />{accent[0].toUpperCase() + accent.slice(1)}</label>)}</fieldset>
      <div className="appearance-fields"><label>Queue density<select value={draft.density} onChange={(event) => change('density', event.target.value as WorkspaceProfile['density'])}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label><label>Default queue view<select value={draft.defaultQueueView} onChange={(event) => change('defaultQueueView', event.target.value as WorkspaceProfile['defaultQueueView'])}><option value="needs_review">Needs review</option><option value="all">All documents</option><option value="processing">Processing</option><option value="approved">Approved</option><option value="failed">Needs retry</option></select></label></div>
      {error && <p className="inline-error" role="alert">{error}</p>}{message && <p className="profile-message" role="status"><Check size={15} />{message}</p>}{storageError && <p className="inline-error" role="alert">{storageError}</p>}
      <div className="appearance-actions"><button className="button button-primary" type="submit">Apply changes <Check size={16} /></button><button className="text-action" type="button" onClick={() => { const persisted = reset(); setDraft({ ...defaults }); setError(null); setMessage(persisted ? 'Installation defaults restored.' : 'Defaults applied for this session.') }}><RotateCcw size={14} /> Reset appearance</button></div>
    </form><aside className={`profile-preview accent-${draft.accent}`}><span className="section-kicker">PROFILE PREVIEW</span><div className="preview-brand"><span><ScanLine size={21} /></span><strong>{draft.productName || 'Product name'}</strong></div><p>{draft.workspaceLabel || workspaceName}</p><div className="preview-record"><span>DOCUMENT REVIEW</span><strong>Source → record → handoff</strong><small>Evidence and versioned approval stay at the heart of every workspace.</small></div><div className="profile-transfer"><strong>Reuse this setup</strong><p>Export the applied profile and import it into another browser or client workspace.</p><button className="button button-secondary" type="button" onClick={() => downloadBlob(new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' }), 'invoicelens-workspace-profile.json')}><Download size={15} /> Export applied profile</button><button className="text-action" type="button" onClick={() => input.current?.click()}><Upload size={15} /> Import profile JSON</button><input ref={input} type="file" accept=".json,application/json" className="sr-only" aria-label="Import workspace profile" onChange={(event) => { void importProfile(event.target.files?.[0]); event.target.value = '' }} /></div><small className="profile-boundary">Appearance only. Server workspace identity, access, extraction, currencies and approval rules are unchanged.</small></aside></div>
  </section>
}
