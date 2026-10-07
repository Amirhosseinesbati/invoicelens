export type ReviewDesign = 'command' | 'studio'

// Local visual calibration only: production callers explicitly disable it.
export function reviewDesignFromHash(hash: string, enabled: boolean): ReviewDesign | undefined {
  if (!enabled) return undefined
  const value = new URLSearchParams(hash.split('?')[1] || '').get('design')
  return value === 'command' || value === 'studio' ? value : undefined
}

export function reviewDesignHref(id: string, design?: ReviewDesign): string {
  return `#/document/${encodeURIComponent(id)}${design ? '?design=' + design : ''}`
}
