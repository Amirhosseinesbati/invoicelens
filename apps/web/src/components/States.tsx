import type { ReactNode } from 'react'
import { AlertCircle, ArrowRight, FileQuestion, LoaderCircle, RefreshCw, ShieldAlert, WifiOff } from 'lucide-react'
import { ApiError } from '../api/client'
import { displayError } from '../lib/format'

export function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'amber' | 'green' | 'red' | 'blue' }) {
  return <span className={`status-pill status-${tone}`}><span className="status-dot" />{children}</span>
}

export function LoadingState({ label = 'Loading workbench…' }: { label?: string }) {
  return <div className="state-panel" role="status"><LoaderCircle size={24} className="spin" /><p>{label}</p></div>
}

export function ErrorState({ error, onRetry, compact = false }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const status = error instanceof ApiError ? error.status : undefined
  const Icon = status === 0 ? WifiOff : status === 403 ? ShieldAlert : AlertCircle
  const title = status === 0 ? 'Connection lost' : status === 403 ? 'Access restricted' : 'Unable to load this view'
  return <div className={`state-panel state-error ${compact ? 'state-compact' : ''}`} role="alert">
    <Icon size={25} />
    <h3>{title}</h3>
    <p>{displayError(error)}</p>
    {onRetry && <button className="button button-secondary" onClick={onRetry}><RefreshCw size={15} /> Retry</button>}
  </div>
}

export function EmptyState({ title, description, action, onAction }: { title: string; description: string; action?: string; onAction?: () => void }) {
  return <div className="state-panel state-empty"><FileQuestion size={28} /><h3>{title}</h3><p>{description}</p>{action && onAction && <button className="text-action" onClick={onAction}>{action} <ArrowRight size={15} /></button>}</div>
}
