import { useId, useSyncExternalStore } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { themeStore, type ThemePreference } from '../lib/theme'
const options = [{ value: 'dark', label: 'Dark', icon: Moon }, { value: 'light', label: 'Light', icon: Sun }, { value: 'system', label: 'System', icon: Monitor }] as const
export function ThemeControl({ detailed = false }: { detailed?: boolean }) {
  const state = useSyncExternalStore(themeStore.subscribe, themeStore.getSnapshot)
  const id = useId()
  const Icon = options.find(option => option.value === state.preference)?.icon ?? Moon
  return <div className={detailed ? 'theme-settings' : 'theme-control'}>
    {detailed && <div><strong>Display theme</strong><p>Choose your workspace lighting. System follows your device; documents keep their original colors.</p></div>}
    <label htmlFor={id} className="theme-label"><Icon size={15} /><span className={detailed ? '' : 'sr-only'}>Display theme</span><select id={id} aria-label="Display theme" value={state.preference} onChange={event => themeStore.setPreference(event.target.value as ThemePreference)}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
    {detailed && <p className="theme-status" role="status">{state.storageAvailable ? `Using ${state.resolved} appearance${state.preference === 'system' ? ', following your device' : ''}. Saved in this browser.` : 'Browser storage is unavailable. Your theme applies for this session.'}</p>}
  </div>
}
