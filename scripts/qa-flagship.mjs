// InvoiceLens flagship calibration: the user's local Chrome, isolated context.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { pathToFileURL, fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const { chromium } = await import(pathToFileURL(process.env.INVOICELENS_PLAYWRIGHT).href)
const before = process.argv.includes('--before')
const dir = path.join(root, 'docs/screenshots/flagship-2026-10-06')
await fs.mkdir(dir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = []
const completed = []
let outcome = 'failed'
let failure = null
page.on('pageerror', e => errors.push(e.message))
const screenshot = async name => {
  await page.mouse.move(0, 0)
  await page.screenshot({ path: path.join(dir, name + '.png') })
}
const step = async (name, run) => { await run(); completed.push(name); console.log('PASS ' + name) }
const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No horizontal overflow')
try {
  await page.goto('http://127.0.0.1:4312')
  await page.getByRole('button', { name: 'Use demo operator' }).click()
  await page.getByRole('button', { name: 'Enter workbench' }).click()
  await page.locator('.primary-nav').waitFor()
  const response = await context.request.get('http://127.0.0.1:4312/api/documents')
  const payload = await response.json()
  const docs = Array.isArray(payload) ? payload : payload.documents || payload.items
  const invoice = docs.find(d => d.kind === 'invoice' && d.filename === 'INV-0004.pdf')
  assert.ok(invoice, 'Synthetic invoice must already exist in isolated preview')
  await page.goto('http://127.0.0.1:4312/#/document/' + invoice.id)
  await page.locator('.source-image-frame img').waitFor()
  await page.evaluate(() => document.fonts.ready)
  await screenshot((before ? 'before' : 'after') + '-desktop-1440')
  const detail = await (await context.request.get('http://127.0.0.1:4312/api/documents/' + invoice.id)).json()
  console.log(JSON.stringify({ invoiceId: invoice.id, fields: Object.keys(detail.fields), findings: detail.findings, lines: detail.lines.length }))
  await page.setViewportSize({ width: 390, height: 844 })
  await screenshot((before ? 'before' : 'after') + '-mobile-390')
  await noOverflow()
  if (!before && !process.argv.includes('--capture-only')) {
    await step('mobile field evidence, persistent action, Escape and navigation focus', async () => {
      await page.locator('.field-select').filter({ hasText: 'Issue date' }).click()
      assert.equal(await page.getByRole('button', { name: 'Document', exact: true }).getAttribute('aria-pressed'), 'true')
      await page.locator('.evidence-box').waitFor()
      assert.equal(await page.locator('.data-footer').isVisible(), true)
      await page.evaluate(() => window.scrollTo(0, 0))
      await screenshot('after-mobile-document-390')
      await page.locator('.source-scroll').focus()
      await page.keyboard.press('Escape')
      assert.equal(await page.getByRole('button', { name: 'Details', exact: true }).getAttribute('aria-pressed'), 'true')
      await page.getByRole('button', { name: 'Open menu', exact: true }).click()
      await page.getByRole('dialog', { name: 'Workspace navigation' }).waitFor()
      await page.keyboard.press('Escape')
      assert.equal(await page.getByRole('button', { name: 'Open menu', exact: true }).getAttribute('aria-expanded'), 'false')
      assert.equal(await page.getByRole('button', { name: 'Open menu', exact: true }).evaluate(e => e === document.activeElement), true)
      await page.keyboard.press('/')
      assert.equal(await page.getByLabel('Search documents').evaluate(e => e === document.activeElement), true)
      await page.getByLabel('Search documents').blur()
      await noOverflow()
    })
    await step('1280 and 768 responsive hierarchy', async () => {
      for (const [width, height] of [[1280, 800], [768, 1024]]) {
        await page.setViewportSize({ width, height })
        await page.evaluate(() => window.scrollTo(0, 0))
        await noOverflow()
        await screenshot('after-responsive-' + width)
      }
    })
    await page.setViewportSize({ width: 1440, height: 900 })
    await step('keyboard tabs, divider, linked finding and fit/zoom', async () => {
      await page.getByRole('tab', { name: 'Details', exact: true }).focus()
      await page.keyboard.press('ArrowRight')
      assert.equal(await page.getByRole('tab', { name: /^Findings/ }).getAttribute('aria-selected'), 'true')
      await screenshot('after-findings-desktop')
      await page.getByRole('button', { name: /Inspect line 1 evidence/ }).click()
      assert.equal(await page.locator('.source-evidence-dock').innerText().then(t => t.includes('Unit Price')), true)
      await page.locator('.evidence-box').waitFor()
      const fit = (await page.locator('.source-canvas').boundingBox()).width
      await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
      assert.ok((await page.locator('.source-canvas').boundingBox()).width > fit)
      await page.getByRole('button', { name: 'Reset zoom', exact: true }).click()
      const separator = page.getByRole('separator', { name: 'Resize source and data panels' })
      const previous = Number(await separator.getAttribute('aria-valuenow'))
      await separator.focus()
      await page.keyboard.press('ArrowRight')
      assert.equal(Number(await separator.getAttribute('aria-valuenow')), previous + 3)
      await page.keyboard.press('ArrowLeft')
      await page.getByRole('tab', { name: 'Details', exact: true }).click()
    })
    const originalDate = detail.fields.date.value
    const syntheticDate = originalDate === '2026-06-17' ? '2026-06-18' : '2026-06-17'
    const editDate = async (value, reason) => {
      await page.getByRole('tab', { name: 'Details', exact: true }).click()
      await page.getByRole('button', { name: 'Edit Issue date', exact: true }).click()
      await page.getByLabel('Correct value', { exact: true }).fill(value)
      await page.getByLabel('Reason for correction').fill(reason)
      await page.getByRole('button', { name: 'Save & revalidate', exact: true }).click()
    }
    await step('correction error retains edit and retry saves a real version', async () => {
      await page.route('**/api/documents/' + invoice.id + '/corrections', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Synthetic QA: correction service temporarily unavailable.' }) }))
      await editDate(syntheticDate, 'Synthetic UI verification: temporary date correction, restored after export.')
      await page.getByRole('alert').filter({ hasText: 'correction service' }).waitFor()
      assert.equal(await page.getByLabel('Correct value', { exact: true }).inputValue(), syntheticDate)
      await screenshot('after-correction-error-desktop')
      await page.unroute('**/api/documents/' + invoice.id + '/corrections')
      await page.getByRole('button', { name: 'Save & revalidate', exact: true }).click()
      await page.getByRole('button', { name: 'Edit Issue date', exact: true }).waitFor()
      const corrected = await (await context.request.get('http://127.0.0.1:4312/api/documents/' + invoice.id)).json()
      assert.equal(corrected.fields.date.value, syntheticDate)
      assert.ok(corrected.version > detail.version)
    })
    await step('resolve real variance, approve server version and download twice', async () => {
      await page.getByRole('tab', { name: /^Findings/ }).click()
      const accept = page.getByRole('button', { name: 'Accept finding', exact: true })
      while (await accept.count()) {
        await accept.first().click()
        await page.waitForFunction(() => !document.querySelector('.finding-actions button:disabled'))
      }
      const approval = page.getByRole('button', { name: /^Approve v/ })
      await approval.waitFor()
      assert.equal(await approval.isEnabled(), true)
      await approval.click()
      await page.getByRole('button', { name: 'Download XLSX', exact: true }).waitFor()
      await screenshot('after-approved-desktop')
      for (let index = 0; index < 2; index++) {
        const event = page.waitForEvent('download')
        await page.getByRole('button', { name: 'Download XLSX', exact: true }).click()
        const download = await event
        const file = path.join(root, 'tmp/flagship-export-' + index + '.xlsx')
        await download.saveAs(file)
        assert.equal((await fs.readFile(file)).subarray(0, 2).toString(), 'PK')
      }
    })
    await step('restore source date, invalidate approval and inspect real activity', async () => {
      await editDate(originalDate, 'Synthetic UI verification complete: restored the original source date.')
      await page.getByRole('button', { name: 'Edit Issue date', exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: 'Download XLSX', exact: true }).count(), 0)
      await page.getByRole('button', { name: /^Approve v/ }).waitFor()
      const restored = await (await context.request.get('http://127.0.0.1:4312/api/documents/' + invoice.id)).json()
      assert.equal(restored.fields.date.value, originalDate)
      assert.notEqual(restored.status, 'approved')
      await page.getByRole('tab', { name: 'Activity', exact: true }).click()
      await page.locator('.timeline-item').first().waitFor()
      await screenshot('after-activity-desktop')
      await page.getByRole('tab', { name: 'Details', exact: true }).click()
      await page.getByRole('button', { name: 'Show evidence for line 1 unit price', exact: true }).click()
      await page.locator('.data-scroll').evaluate(e => { e.scrollTop = 0 })
      await page.evaluate(() => window.scrollTo(0, 0))
      await screenshot('after-desktop-1440')
      await page.setViewportSize({ width: 390, height: 844 })
      await screenshot('after-mobile-390')
      await page.getByRole('button', { name: 'Document', exact: true }).click()
      await page.locator('.source-image-frame img').waitFor()
      await screenshot('after-mobile-document-390')
      await noOverflow()
    })
  }
  assert.deepEqual(errors, [])
  outcome = 'passed'
} catch (error) {
  failure = error.message
  await screenshot('failure-state')
  throw error
} finally {
  await fs.writeFile(path.join(dir, before ? 'baseline-result.json' : process.argv.includes('--capture-only') ? 'capture-result.json' : 'qa-result.json'), JSON.stringify({ outcome, browser: 'user local Chrome; isolated headless context', completed, pageErrors: errors, failure, finishedAt: new Date().toISOString() }, null, 2))
  await browser.close()
}
