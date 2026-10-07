import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BriefcaseBusiness, FileClock, FileStack, Inbox, LayoutGrid, LogOut, Menu, ScanLine, Search, Settings2, UploadCloud, Wifi, WifiOff, X } from 'lucide-react'
import { ApiError, api } from './api/client'
import type { User } from './api/types'
import { LoginPage } from './features/auth/LoginPage'
import { OverviewPage } from './features/overview/OverviewPage'
import { QueuePage } from './features/queue/QueuePage'
import { IntakePage } from './features/intake/IntakePage'
import { ReviewPage } from './features/review/ReviewPage'
import { VendorsPage } from './features/vendors/VendorsPage'
import { ExportsPage } from './features/exports/ExportsPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { LoadingState, StatusPill } from './components/States'
import { WorkspaceProvider, useWorkspace } from './components/WorkspaceProvider'
import { initials } from './lib/format'
import { queueViewFromHash } from './lib/queue'
import { reviewDesignFromHash, type ReviewDesign } from './lib/design-lab'
import { ThemeControl } from './components/ThemeControl'
import { DesignPreviewControl } from './features/review/DesignPreview'

type Route = { view: 'overview' | 'queue' | 'intake' | 'vendors' | 'exports' | 'settings' } | { view: 'document'; id: string; design?: ReviewDesign }

function parseRoute(): Route {
  const hash = window.location.hash.slice(1).split('?')[0]
  if (hash.startsWith('/document/')) {
    try { return { view: 'document', id: decodeURIComponent(hash.slice('/document/'.length)), design: reviewDesignFromHash(window.location.hash, import.meta.env.DEV) } } catch { return { view: 'queue' } }
  }
  if (['queue', 'intake', 'vendors', 'exports', 'settings'].includes(hash.slice(1))) return { view: hash.slice(1) as 'queue' | 'intake' | 'vendors' | 'exports' | 'settings' }
  return { view: 'overview' }
}

export function navigate(view: Route['view'] | string, id?: string): void {
  window.location.hash = view === 'document' && id ? `/document/${encodeURIComponent(id)}` : `/${view}`
}

const navigation = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid },
  { id: 'queue', label: 'Review queue', icon: Inbox },
  { id: 'intake', label: 'Batch intake', icon: UploadCloud },
  { id: 'vendors', label: 'Vendors', icon: BriefcaseBusiness },
  { id: 'exports', label: 'Exports', icon: FileStack },
  { id: 'settings', label: 'Settings', icon: Settings2 },
] as const

function Workbench({ user, onLogout }: { user: User; onLogout: () => void }) {
  const { profile, workspaceName } = useWorkspace()
  const [route, setRoute] = useState<Route>(parseRoute)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [search, setSearch] = useState('')
  const sidebarRef = useRef<HTMLElement>(null)
  const menuRef = useRef<HTMLButtonElement>(null)
  const queryClient = useQueryClient()
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.overview, refetchInterval: 15_000 })
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings, retry: false, refetchInterval: 30_000 })
  useEffect(() => {
    const update = () => { setRoute(parseRoute()); setMobileOpen(false); window.scrollTo({ top: 0, behavior: 'instant' }) }
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  const active = route.view === 'document' ? 'queue' : route.view
  const title = route.view === 'document' ? 'Document review' : navigation.find((item) => item.id === route.view)?.label ?? 'Overview'
  useEffect(() => { document.title = `${title} · ${profile.productName}` }, [title, profile.productName])
  useEffect(() => {
    if (!mobileOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const items = () => Array.from(sidebarRef.current?.querySelectorAll<HTMLButtonElement>('button') || []).filter((button) => button.offsetParent !== null)
    items()[0]?.focus()
    const trap = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMobileOpen(false); return }
      if (event.key !== 'Tab') return
      const buttons = items(); const first = buttons[0]; const last = buttons.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', trap)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', trap); menuRef.current?.focus() }
  }, [mobileOpen])
  const connected = overview.isSuccess && settings.isSuccess
  const checkingConnection = overview.isPending || settings.isPending
  const readOnly = user.role === 'viewer'
  const page = useMemo(() => {
    switch (route.view) {
      case 'overview': return <OverviewPage onOpenDocument={(id) => navigate('document', id)} onNavigate={navigate} />
      case 'queue': return <QueuePage key={window.location.hash} initialView={queueViewFromHash(window.location.hash, profile.defaultQueueView)} search={search} onSearch={setSearch} onOpenDocument={(id) => navigate('document', id)} onNavigate={navigate} />
      case 'intake': return <IntakePage readOnly={readOnly} onOpenDocument={(id) => navigate('document', id)} />
      case 'vendors': return <VendorsPage onOpenDocument={(id) => navigate('document', id)} />
      case 'exports': return <ExportsPage readOnly={readOnly} onOpenDocument={(id) => navigate('document', id)} />
      case 'settings': return <SettingsPage user={user} />
      case 'document': return <ReviewPage key={route.id} id={route.id} design={route.design ?? 'command'} previewDesign={route.design} readOnly={readOnly} onBack={() => navigate('queue')} />
    }
  }, [route, search, readOnly, user, profile.defaultQueueView])
  return <div className={`app-shell finance-shell ${route.view === 'document' && route.design ? '' : 'command-shell'} ${route.view === 'document' ? 'is-review' : ''} ${route.view === 'document' && route.design ? 'design-' + route.design : ''}`}>
    <a className="skip-link" href="#workspace-content" onClick={(event) => { event.preventDefault(); document.getElementById('workspace-content')?.focus() }}>Skip to content</a>
    <aside ref={sidebarRef} id="workspace-navigation" role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen ? true : undefined} aria-label="Workspace navigation" className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><span className="brand-mark"><ScanLine size={21} strokeWidth={2.2} /></span><span className="brand-name">{profile.productName}</span><button className="icon-button sidebar-close" aria-label="Close menu" onClick={() => setMobileOpen(false)}><X size={19} /></button></div>
      <button className="workspace-switch" onClick={() => navigate('settings')} title="Customize workspace"><span className="workspace-avatar">{initials(workspaceName)}</span><span><strong>{workspaceName}</strong><small>Operations workspace</small></span><Settings2 size={14} /></button>
      <div className="sidebar-caption">WORKSPACE</div>
      <nav aria-label="Primary navigation" className="primary-nav">
        {navigation.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-label={label} title={label} aria-current={active === id ? 'page' : undefined} className={`nav-link ${active === id ? 'nav-active' : ''}`} onClick={() => navigate(id)}><Icon size={18} strokeWidth={1.9} /><span>{label}</span>{id === 'queue' && overview.data && overview.data.needs_review > 0 && <b>{overview.data.needs_review}</b>}</button>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="demo-note"><span className="demo-note-line" /> {settings.data?.mode === 'DEMO' ? 'SYNTHETIC DEMO DATASET' : 'EVIDENCE-FIRST REVIEW'}<p>{settings.data?.mode === 'DEMO' ? 'All documents and vendors in this workspace are fictional.' : 'Review source evidence before approving a record.'}</p></div>
        <div className="user-tile"><span className="user-avatar">{user.email.slice(0, 2).toUpperCase()}</span><span className="user-meta"><strong>{user.email}</strong><small>{user.role} access</small></span><button className="icon-button" aria-label="Sign out" title="Sign out" onClick={onLogout}><LogOut size={17} /></button></div>
      </div>
    </aside>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMobileOpen(false)} />}
    <div className="main-column">
      <header className="topbar">
        <div className="topbar-left"><button ref={menuRef} className="icon-button mobile-menu" aria-label="Open menu" aria-expanded={mobileOpen} aria-controls="workspace-navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button><span className="topbar-breadcrumb">{workspaceName}</span><span className="breadcrumb-slash">/</span><strong>{title}</strong></div>
        <div className="topbar-actions"><ThemeControl />{import.meta.env.DEV && route.view === 'document' && route.design && <DesignPreviewControl id={route.id} design={route.design} demo={settings.data?.mode === 'DEMO'} />}{settings.data?.mode === 'DEMO' && <span className="shell-demo-label" title="Fictional documents with a local model simulation">Synthetic demo</span>}
          <form className="top-search" onSubmit={(event) => { event.preventDefault(); navigate('queue?status=all') }}><Search size={17} /><input aria-label="Search documents" placeholder="Find a document…" value={search} onChange={(event) => setSearch(event.target.value)} /><kbd aria-hidden="true">/</kbd></form>
          <StatusPill tone={checkingConnection ? 'blue' : connected ? 'green' : 'red'}>{checkingConnection ? 'Checking connection' : connected ? <><Wifi size={13} /> Connected</> : <><WifiOff size={13} /> Disconnected</>}</StatusPill>
          <button className="top-avatar" title={user.email} onClick={() => navigate('settings')}>{user.email.slice(0, 2).toUpperCase()}</button>
        </div>
      </header>
      {route.view !== 'document' && settings.data?.mode.toUpperCase() === 'DEMO' && <div className="demo-banner"><span>DEMO MODE</span> Synthetic documents · local model simulation</div>}
      <div id="workspace-content" tabIndex={-1}>{page}</div>
      <footer className="app-footer"><span>{profile.productName} / {workspaceName}</span><span><FileClock size={13} /> Evidence-first document operations</span></footer>
    </div>
    <button className="sr-only focus-visible-control" onClick={() => { queryClient.invalidateQueries() }}>Refresh all data</button>
  </div>
}

export function App() {
  const queryClient = useQueryClient()
  const [sessionUser, setSessionUser] = useState<User | null>(null)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const me = useQuery({ queryKey: ['auth', 'me'], queryFn: api.me, retry: false, enabled: !sessionUser })
  const user = sessionUser ?? me.data
  const onLogout = async () => {
    try { await api.logout() } catch { setLogoutError('Sign out failed. Reconnect and try again to end your server session.'); return }
    setLogoutError(null)
    setSessionUser(null)
    queryClient.clear()
    window.location.hash = '/overview'
    await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
  }
  useEffect(() => {
    const searchShortcut = (event: KeyboardEvent) => {
      if (event.key === '/' && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault(); document.querySelector<HTMLInputElement>('.top-search input')?.focus()
      }
    }
    document.addEventListener('keydown', searchShortcut)
    return () => document.removeEventListener('keydown', searchShortcut)
  }, [])
  if (!user && me.isPending) return <div className="boot-screen"><ThemeControl /><div className="brand"><span className="brand-mark"><ScanLine size={22} /></span>Invoice<strong>Lens</strong></div><LoadingState label="Connecting to your workspace…" /></div>
  if (!user && me.isError && (!(me.error instanceof ApiError) || me.error.status !== 401)) return <div className="boot-screen"><ThemeControl /><div className="brand"><span className="brand-mark"><ScanLine size={22} /></span>Invoice<strong>Lens</strong></div><div className="boot-error"><WifiOff size={24} /><h1>Unable to reach InvoiceLens</h1><p>{me.error instanceof Error ? me.error.message : 'The API is unavailable.'}</p><button className="button button-primary" onClick={() => me.refetch()}>Retry connection</button></div></div>
  if (!user) return <LoginPage onLogin={(loggedInUser) => { setSessionUser(loggedInUser); queryClient.setQueryData(['auth', 'me'], loggedInUser); queryClient.invalidateQueries() }} />
  return <WorkspaceProvider key={user.workspace_id} workspaceId={user.workspace_id} workspaceName={user.workspace_name}>{logoutError && <div className="session-error" role="alert">{logoutError}<button className="text-action" onClick={() => setLogoutError(null)}>Dismiss</button></div>}<Workbench user={user} onLogout={onLogout} /></WorkspaceProvider>
}
