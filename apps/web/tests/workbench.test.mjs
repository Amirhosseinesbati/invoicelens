import assert from 'node:assert/strict'
import test from 'node:test'
import { inQueueView, queueViewFromHash, selectDocuments } from '../src/lib/queue.ts'
import { defaultProfile, loadProfile, parseProfile, profileKey } from '../src/lib/workspace-profile.ts'
import { maxFileBytes, prepareSelection } from '../src/lib/intake.ts'

const doc = (id, patch = {}) => ({ id, filename: id + '.pdf', kind: 'invoice', status: 'needs_review', vendor: 'Harbor Supply', number: 'INV-' + id, date: null, currency: 'USD', total: '100.00', version: 1, page_count: 1, findings_count: 0, created_at: '2026-10-06T12:00:00Z', ...patch })
test('processing includes queued and uploaded records; retry includes cancellation', () => {
  for (const status of ['queued', 'processing', 'uploaded']) assert.equal(inQueueView(doc('1', { status }), 'processing'), true)
  for (const status of ['failed', 'cancelled']) assert.equal(inQueueView(doc('1', { status }), 'failed'), true)
  assert.equal(inQueueView(doc('1'), 'processing'), false)
})
test('priority sorts findings then oldest receipt without changing cached records', () => {
  const records = [doc('new', { findings_count: 2 }), doc('old', { findings_count: 2, created_at: '2026-10-01T12:00:00Z' }), doc('critical', { findings_count: 4 })]
  assert.deepEqual(selectDocuments(records, 'needs_review', '', 'all', 'priority').map((item) => item.id), ['critical', 'old', 'new'])
  assert.equal(records[0].id, 'new')
})
test('search and type combine with stage; cleared search returns all records', () => {
  const records = [doc('1'), doc('2', { kind: 'purchase_order', status: 'approved' }), doc('3', { vendor: null })]
  assert.equal(selectDocuments(records, 'all', '  HARBOR  ', 'purchase_order', 'newest').length, 1)
  assert.equal(selectDocuments(records, 'needs_review', 'purchase order', 'all', 'newest').length, 0)
  assert.equal(selectDocuments(records, 'all', '', 'all', 'newest').length, 3)
  assert.equal(selectDocuments(records, 'all', 'INV-3', 'all', 'newest')[0].id, '3')
})
test('stage links validate query parameters and respect a workspace default', () => {
  assert.equal(queueViewFromHash('#/queue?status=failed', 'all'), 'failed')
  assert.equal(queueViewFromHash('#/queue?status=invalid', 'approved'), 'approved')
  assert.equal(queueViewFromHash('#/queue', 'processing'), 'processing')
})
test('profile import roundtrips, trims labels and drops unrecognized fields', () => {
  const imported = parseProfile({ ...defaultProfile, productName: '  Client Desk  ', accent: 'teal', apiKey: 'ignored', workspace_id: 'ignored' })
  assert.equal(imported.productName, 'Client Desk')
  assert.equal('apiKey' in imported, false)
  assert.deepEqual(parseProfile(JSON.parse(JSON.stringify(imported))), imported)
})
test('profile rejects unsupported versions, malformed choices and excessive labels', () => {
  for (const patch of [{ schemaVersion: 2 }, { productName: '' }, { productName: 'a'.repeat(33) }, { workspaceLabel: 'bad\nlabel' }, { density: 'tiny' }, { accent: '#fff' }, { defaultQueueView: 'secret' }]) assert.throws(() => parseProfile({ ...defaultProfile, ...patch }))
  assert.throws(() => parseProfile(null))
  assert.throws(() => parseProfile([]))
})
test('browser preferences are scoped; corrupted or inaccessible storage falls back', () => {
  const saved = new Map([[profileKey('workspace-a'), JSON.stringify({ ...defaultProfile, accent: 'copper' })]])
  const storage = { getItem: (key) => saved.get(key) ?? null }
  assert.equal(loadProfile(storage, 'workspace-a').accent, 'copper')
  assert.deepEqual(loadProfile(storage, 'workspace-b'), defaultProfile)
  assert.deepEqual(loadProfile({ getItem: () => '{broken' }, 'workspace-a'), defaultProfile)
  assert.deepEqual(loadProfile({ getItem: () => { throw new Error('blocked') } }, 'workspace-a'), defaultProfile)
})
const file = (name, patch = {}) => ({ name, type: 'application/pdf', size: 100, lastModified: 1, ...patch })
test('intake deduplicates selection and preserves the existing batch', () => {
  const current = [file('a.pdf')]
  assert.equal(prepareSelection(current, [file('a.pdf'), file('b.pdf'), file('b.pdf')]).length, 2)
  assert.equal(current.length, 1)
})
test('intake rejects oversized, empty and unsupported files before submission', () => {
  for (const invalid of [file('a.pdf', { size: maxFileBytes + 1 }), file('empty.pdf', { size: 0 }), file('a.exe', { type: 'application/octet-stream' })]) assert.throws(() => prepareSelection([], [invalid]))
  assert.equal(prepareSelection([], [file('native.PDF', { type: '' })]).length, 1)
})
test('intake never silently truncates a batch at the limit', () => {
  const current = Array.from({ length: 30 }, (_, index) => file(index + '.pdf'))
  assert.throws(() => prepareSelection(current, [file('extra.pdf')]), /no files.*added/)
  assert.equal(current.length, 30)
})
