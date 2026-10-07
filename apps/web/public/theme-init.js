/* Same-origin synchronous head script. No inline styles/scripts or document data. */
(() => {
  const key = 'invoicelens:theme:v1'
  const valid = value => ['dark', 'light', 'system'].includes(value)
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const listeners = new Set()
  let preference = 'dark', storageAvailable = true, watching = false
  try { const saved = window.localStorage.getItem(key); if (valid(saved)) preference = saved } catch { storageAvailable = false }
  let snapshot
  const apply = () => {
    const resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
    document.documentElement.dataset.theme = resolved
    document.documentElement.dataset.themePreference = preference
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', resolved === 'dark' ? '#0c1220' : '#f1f4f9')
    if (!snapshot || snapshot.preference !== preference || snapshot.resolved !== resolved || snapshot.storageAvailable !== storageAvailable) {
      snapshot = Object.freeze({ preference, resolved, storageAvailable }); listeners.forEach(listener => listener())
    }
  }
  const osChange = () => { if (preference === 'system') apply() }
  const watch = () => {
    if (preference === 'system' && !watching) { media.addEventListener('change', osChange); watching = true }
    else if (preference !== 'system' && watching) { media.removeEventListener('change', osChange); watching = false }
  }
  const setPreference = value => {
    if (!valid(value)) return
    preference = value
    try { window.localStorage.setItem(key, value); storageAvailable = true } catch { storageAvailable = false }
    watch(); apply()
  }
  window.addEventListener('storage', event => {
    if (event.key !== key) return
    preference = valid(event.newValue) ? event.newValue : 'dark'; watch(); apply()
  })
  watch(); apply()
  window.invoiceLensTheme = Object.freeze({ getSnapshot: () => snapshot, subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener) }, setPreference })
})()
