import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { defaultProfile, loadProfile, parseProfile, profileKey, type WorkspaceProfile } from '../lib/workspace-profile'

const installationProfile = (() => {
  try { return parseProfile({ ...defaultProfile, productName: import.meta.env.VITE_PRODUCT_NAME || defaultProfile.productName, workspaceLabel: import.meta.env.VITE_WORKSPACE_LABEL || '', accent: import.meta.env.VITE_ACCENT || 'indigo' }) }
  catch { return { ...defaultProfile } }
})()
interface WorkspaceContext {
  profile: WorkspaceProfile
  defaults: WorkspaceProfile
  workspaceName: string
  save: (profile: WorkspaceProfile) => boolean
  reset: () => boolean
  storageError: string | null
}
const Context = createContext<WorkspaceContext | null>(null)

export function WorkspaceProvider({ workspaceId, workspaceName, children }: { workspaceId: string; workspaceName: string; children: ReactNode }) {
  const [profile, setProfile] = useState(() => {
    try { return loadProfile(window.localStorage, workspaceId, installationProfile) } catch { return { ...installationProfile } }
  })
  const [storageError, setStorageError] = useState<string | null>(null)
  const save = (next: WorkspaceProfile) => {
    const valid = parseProfile(next)
    setProfile(valid)
    try { window.localStorage.setItem(profileKey(workspaceId), JSON.stringify(valid)); setStorageError(null); return true }
    catch { setStorageError('Browser storage is unavailable. Your appearance changes apply for this session; export a profile to keep them.'); return false }
  }
  useEffect(() => {
    document.documentElement.dataset.accent = profile.accent
    document.documentElement.dataset.density = profile.density
    return () => { delete document.documentElement.dataset.accent; delete document.documentElement.dataset.density }
  }, [profile.accent, profile.density])
  return <Context.Provider value={{ profile, defaults: installationProfile, workspaceName: profile.workspaceLabel || workspaceName, save, reset: () => save({ ...installationProfile }), storageError }}>{children}</Context.Provider>
}

export function useWorkspace(): WorkspaceContext {
  const context = useContext(Context)
  if (!context) throw new Error('WorkspaceProvider is required.')
  return context
}
