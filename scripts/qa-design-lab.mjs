// Actual local UI, isolated Chrome; synthetic records only. No browser install.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { pathToFileURL, fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const { chromium } = await import(pathToFileURL(process.env.INVOICELENS_PLAYWRIGHT).href)
const dir = path.join(root, process.env.INVOICELENS_DESIGN_QA_DIR || 'docs/screenshots/design-lab-2026-10-07')
await fs.mkdir(dir, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = []
const completed = []
let outcome = 'failed', failure = null
page.on('pageerror', error => errors.push(error.message))
const shot = async name => { await page.mouse.move(0, 0); await page.screenshot({ path: path.join(dir, name + '.png') }) }
try {
  await page.goto('http://127.0.0.1:4312')
  await page.getByRole('button', { name: 'Use demo operator' }).click()
  await page.getByRole('button', { name: 'Enter workbench' }).click()
  await page.locator('.primary-nav').waitFor()
  const docs = await (await context.request.get('http://127.0.0.1:4312/api/documents')).json()
  const invoice = docs.find(doc => doc.kind === 'invoice' && doc.filename === 'INV-0004.pdf')
  assert.ok(invoice, 'Real synthetic review fixture is required')
  for (const design of ['command', 'studio']) {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('http://127.0.0.1:4312/#/overview')
    await page.locator('.operations-hero').waitFor()
    await page.goto('http://127.0.0.1:4312/#/document/' + invoice.id + '?design=' + design)
    await page.locator('.design-' + design).waitFor()
    await page.locator('.source-image-frame img').waitFor()
    await page.evaluate(() => document.fonts.ready)
    await page.getByRole('tab', { name: design === 'command' ? /^Findings/ : 'Details', exact: design !== 'command' }).click()
    await shot(design + '-desktop-1440')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    if (!process.argv.includes('--capture-only')) {
      await page.getByRole('tab', { name: 'Details', exact: true }).click()
      await page.locator('.field-select').filter({ hasText: 'Issue date' }).click()
      await page.locator('.evidence-box').waitFor()
      await page.getByRole('button', { name: 'Edit Issue date', exact: true }).click()
      await page.getByLabel('Correct value', { exact: true }).waitFor()
      await page.keyboard.press('Escape')
      assert.equal(await page.locator('.edit-form').count(), 0)
      await page.getByRole('tab', { name: 'Details', exact: true }).focus()
      await page.keyboard.press('ArrowRight')
      assert.equal(await page.getByRole('tab', { name: /^Findings/ }).getAttribute('aria-selected'), 'true')
      const approve = page.getByRole('button', { name: /^Approve v/ })
      assert.equal(await approve.isDisabled(), true, 'Real blocking variance disables approval')
      await page.getByRole('button', { name: /Inspect line 1 evidence/ }).click()
      completed.push(design + ': fields, correction Escape, keyboard tabs, real approval barrier')
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Document', exact: true }).click()
    await page.locator('.source-image-frame img').waitFor()
    await page.evaluate(() => window.scrollTo(0, 0))
    await shot(design + '-mobile-390')
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    assert.equal(await page.locator('.data-footer').isVisible(), true)
    assert.equal(await page.locator('.design-preview-control').isVisible(), true)
    const dock = await page.locator('.source-evidence-dock').boundingBox()
    const footer = await page.locator('.data-footer').boundingBox()
    assert.ok(dock && footer && dock.y + dock.height <= footer.y + 2, 'Evidence dock stays above the mobile action')
    if (!process.argv.includes('--capture-only')) {
      await page.locator('.source-scroll').focus()
      await page.keyboard.press('Escape')
      assert.equal(await page.getByRole('button', { name: 'Details', exact: true }).getAttribute('aria-pressed'), 'true')
      await page.getByRole('button', { name: 'Open menu', exact: true }).click()
      await page.getByRole('dialog', { name: 'Workspace navigation' }).waitFor()
      await page.keyboard.press('Escape')
      assert.equal(await page.getByRole('button', { name: 'Open menu', exact: true }).getAttribute('aria-expanded'), 'false')
      completed.push(design + ': mobile source, persistent action, no overflow and menu Escape')
    }
  }
  await page.goto('http://127.0.0.1:4312/#/document/' + invoice.id)
  assert.equal(await page.locator('.design-command,.design-studio').count(), 0, 'Current design is preserved')
  assert.deepEqual(errors, [])
  completed.push('Current-design escape route and zero JavaScript page errors')
  outcome = 'passed'
} catch (error) { failure = error.message; await shot('failure-state'); throw error }
finally {
  await fs.writeFile(path.join(dir, process.argv.includes('--capture-only') ? 'capture-result.json' : 'qa-result.json'), JSON.stringify({ outcome, completed, pageErrors: errors, failure, browser: 'user local Chrome, isolated headless context', finishedAt: new Date().toISOString() }, null, 2))
  await browser.close()
}
