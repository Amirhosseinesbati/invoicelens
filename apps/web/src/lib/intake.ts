export const maxBatchFiles = 30
export const maxFileBytes = 20 * 1024 * 1024
type IntakeFile = Pick<File, 'name' | 'type' | 'size' | 'lastModified'>
const allowedTypes = new Set(['application/pdf', 'image/png', 'image/jpeg'])

export function prepareSelection<T extends IntakeFile>(current: T[], incoming: T[]): T[] {
  const identity = (file: T) => JSON.stringify([file.name, file.size, file.lastModified])
  const seen = new Set(current.map(identity))
  const additions = incoming.filter((file) => {
    const key = identity(file)
    if (seen.has(key)) return false
    seen.add(key); return true
  })
  for (const file of additions) {
    if (!allowedTypes.has(file.type) && !/\.(pdf|png|jpe?g)$/i.test(file.name)) throw new Error(`${file.name} is not a PDF, PNG, or JPEG file.`)
    if (!file.size) throw new Error(`${file.name} is empty. Choose a file with document content.`)
    if (file.size > maxFileBytes) throw new Error(`${file.name} exceeds the 20 MB per-file limit.`)
  }
  if (current.length + additions.length > maxBatchFiles) throw new Error('A batch supports 30 files. Submit or remove the current selection before adding more; no files from this selection were added.')
  return [...current, ...additions]
}
