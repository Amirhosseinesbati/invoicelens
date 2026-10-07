export const accents = ['indigo', 'teal', 'copper'] as const
export const queueViews = ['needs_review', 'all', 'processing', 'approved', 'failed'] as const
export type QueueView = typeof queueViews[number]
export interface WorkspaceProfile {
  schemaVersion: 1
  productName: string
  workspaceLabel: string
  accent: typeof accents[number]
  density: 'comfortable' | 'compact'
  defaultQueueView: QueueView
}

export const defaultProfile: WorkspaceProfile = {
  schemaVersion: 1, productName: 'InvoiceLens', workspaceLabel: '',
  accent: 'indigo', density: 'comfortable', defaultQueueView: 'needs_review',
}

// Keep imported configuration deliberately small and allowlisted. No secrets, HTML,
// URLs, or document data are imported into the client profile.
export function parseProfile(value: unknown): WorkspaceProfile {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Choose a valid InvoiceLens profile JSON file.')
  const input = value as Record<string, unknown>
  if (input.schemaVersion !== 1) throw new Error('This profile version is not supported. Expected schemaVersion 1.')
  const text = (key: string, max: number, required: boolean) => {
    const item = input[key]
    if (typeof item !== 'string' || item.length > max || Array.from(item).some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127) || (required && !item.trim())) throw new Error(`Check ${key}: use ${required ? '1' : '0'}–${max} plain-text characters.`)
    return item.trim()
  }
  if (!accents.includes(input.accent as WorkspaceProfile['accent'])) throw new Error('Choose an indigo, teal, or copper accent.')
  if (!['comfortable', 'compact'].includes(String(input.density))) throw new Error('Choose comfortable or compact density.')
  if (!queueViews.includes(input.defaultQueueView as QueueView)) throw new Error('Choose a supported default queue view.')
  return {
    schemaVersion: 1, productName: text('productName', 32, true), workspaceLabel: text('workspaceLabel', 64, false),
    accent: input.accent as WorkspaceProfile['accent'], density: input.density as WorkspaceProfile['density'], defaultQueueView: input.defaultQueueView as QueueView,
  }
}

export function profileKey(workspaceId: string): string { return `invoicelens:profile:v1:${workspaceId}` }

export function loadProfile(storage: Pick<Storage, 'getItem'>, workspaceId: string, defaults = defaultProfile): WorkspaceProfile {
  try { const saved = storage.getItem(profileKey(workspaceId)); return saved ? parseProfile(JSON.parse(saved)) : { ...defaults } }
  catch { return { ...defaults } }
}
