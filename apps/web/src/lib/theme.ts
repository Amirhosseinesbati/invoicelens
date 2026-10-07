export type ThemePreference = 'dark' | 'light' | 'system'
export interface ThemeSnapshot { preference: ThemePreference; resolved: 'dark' | 'light'; storageAvailable: boolean }
export interface ThemeStore {
  getSnapshot: () => ThemeSnapshot
  subscribe: (listener: () => void) => () => void
  setPreference: (preference: ThemePreference) => void
}
declare global { interface Window { invoiceLensTheme: ThemeStore } }
export const themeStore = window.invoiceLensTheme
