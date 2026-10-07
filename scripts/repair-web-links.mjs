// Repair only stale Windows junctions after moving this checkout. No downloads.
// Dry run by default; pass --apply after reviewing the reported local targets.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const modules = path.join(project, 'apps', 'web', 'node_modules')
const apply = process.argv.includes('--apply')
const candidates = []
const missing = []
function inspect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const link = path.join(directory, entry.name)
    if (entry.isSymbolicLink()) {
      const original = fs.readlinkSync(link)
      const normalized = original.replaceAll('\\', '/')
      const marker = '/apps/web/node_modules/'
      const index = normalized.lastIndexOf(marker)
      if (index < 0) continue
      const target = path.resolve(modules, normalized.slice(index + marker.length))
      if (!target.startsWith(modules + path.sep) || !link.startsWith(modules + path.sep)) throw new Error('Refusing a path outside this project’s web dependencies.')
      if (path.resolve(original) === target) continue
      if (!fs.existsSync(target)) { missing.push(path.relative(modules, link)); continue }
      candidates.push({ link, original, target })
    } else if (entry.isDirectory()) inspect(link)
  }
}
inspect(modules)
console.log(JSON.stringify({ mode: apply ? 'apply' : 'dry-run', staleLinks: candidates.length, missingLocalTargets: missing, sample: candidates.slice(0, 3) }, null, 2))
if (missing.length) throw new Error('Some package targets are absent; repair cannot substitute for a locked dependency install.')
if (apply) {
  for (const { link, original, target } of candidates) {
    if (!fs.lstatSync(link).isSymbolicLink()) throw new Error('Refusing to replace a real directory: ' + link)
    fs.unlinkSync(link)
    try { fs.symlinkSync(target, link, process.platform === 'win32' ? 'junction' : 'dir') }
    catch (error) { fs.symlinkSync(original, link, process.platform === 'win32' ? 'junction' : 'dir'); throw error }
  }
  console.log('Repaired ' + candidates.length + ' local dependency links.')
}
