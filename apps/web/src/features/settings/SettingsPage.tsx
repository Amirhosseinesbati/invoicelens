import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleHelp, CircleMinus, Database, FileDown, Fingerprint, ScanLine, ServerCog, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import type { User } from '../../api/types'
import { ErrorState, LoadingState, StatusPill } from '../../components/States'

function SettingRow({ icon: Icon, name, detail, ready, unverified = false }: { icon: typeof Database; name: string; detail: string; ready?: boolean; unverified?: boolean }) {
  const tone = ready ? (unverified ? 'neutral' : 'green') : 'amber'
  return <div className="setting-row"><span className="setting-icon"><Icon size={18} /></span><div><strong>{name}</strong><small>{detail}</small></div>{ready === undefined ? null : <StatusPill tone={tone}>{ready ? (unverified ? <><CircleHelp size={12} /> Configured · unverified</> : <><CircleCheck size={12} /> Available</>) : <><CircleMinus size={12} /> Not configured</>}</StatusPill>}</div>
}

export function SettingsPage({ user }: { user: User }) {
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings, refetchInterval: 30_000 })
  if (settings.isPending) return <main className="page"><LoadingState label="Loading configuration status…" /></main>
  if (settings.isError) return <main className="page"><ErrorState error={settings.error} onRetry={() => settings.refetch()} /></main>
  return <main className="page settings-page"><div className="page-head compact"><div><span className="eyebrow"><span className="eyebrow-line" /> WORKSPACE CONFIGURATION</span><h1>Settings & connections<span className="title-period">.</span></h1><p>Current capabilities reported by the local API. Secrets and model IDs stay on the server.</p></div><ServerCog size={36} strokeWidth={1.3} className="settings-head-icon" /></div>
    <div className="settings-grid"><section className="surface"><div className="section-heading"><div><span className="section-kicker">INSTALLATION</span><h2>Service configuration</h2></div></div><SettingRow icon={Database} name="Workspace" detail={settings.data.workspace_name || user.workspace_name} /><SettingRow icon={ScanLine} name="Operating mode" detail={settings.data.mode.toUpperCase() === 'DEMO' ? 'DEMO · synthetic data and local model fixtures' : 'CONNECTED · live adapters configured; health unverified'} /><SettingRow icon={Fingerprint} name="Model adapter" detail={settings.data.model_configured ? 'Model credentials detected by API; connection not tested' : 'No live model credentials configured'} ready={settings.data.model_configured} unverified /><SettingRow icon={CircleCheck} name="OCR pipeline" detail={settings.data.ocr_available ? 'OCR capability is available' : 'OCR dependency is unavailable'} ready={settings.data.ocr_available} /><SettingRow icon={FileDown} name="Export formats" detail={settings.data.export_formats.join(' · ').toUpperCase() || 'None configured'} ready={settings.data.export_formats.length > 0} /></section>
      <section className="surface"><div className="section-heading"><div><span className="section-kicker">ACCESS</span><h2>Your session</h2></div></div><SettingRow icon={ShieldCheck} name="Signed in as" detail={user.email} /><SettingRow icon={Fingerprint} name="Role" detail={`${user.role[0].toUpperCase()}${user.role.slice(1)} access`} /><SettingRow icon={Database} name="Workspace scope" detail={`Workspace ID: ${user.workspace_id}`} /><div className="settings-note"><strong>Customer installation</strong><p>Provider credentials, retention settings, and workspace configuration are managed through server environment variables and deployment procedures.</p></div></section></div>
  </main>
}
