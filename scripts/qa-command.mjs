// InvoiceLens production Command QA; isolated user-local Chrome, synthetic data only.
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { pathToFileURL, fileURLToPath } from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const {chromium}=await import(pathToFileURL(process.env.INVOICELENS_PLAYWRIGHT).href)
const dir=path.join(root,'docs/screenshots/command-themes-'+new Date().toISOString().slice(0,10))
await fs.mkdir(dir,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
const context=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'reduce',colorScheme:'light'})
const page=await context.newPage(), errors=[], checks=[], requests=[]
page.on('pageerror',error=>errors.push(error.message))
page.on('request',request=>{if(request.url().includes('/api/'))requests.push(request.url())})
const captureOnly=process.argv.includes('--capture-only')
const shot=async name=>{await page.evaluate(()=>document.fonts.ready);await page.mouse.move(0,0);await page.screenshot({path:path.join(dir,name+'.png')})}
const theme=async value=>{await page.getByRole('combobox',{name:'Display theme'}).first().selectOption(value);await page.waitForFunction(value=>document.documentElement.dataset.themePreference===value,value)}
const noOverflow=async label=>assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,label+' overflow')
const goto=async(route,ready)=>{await page.goto('http://127.0.0.1:4312/#/'+route);await page.locator(ready).waitFor();await noOverflow(route)}
let outcome='failed',failure=null
try{
  await page.goto('http://127.0.0.1:4312')
  await page.getByRole('button',{name:'Use demo operator'}).waitFor()
  assert.equal(await page.locator('html').getAttribute('data-theme'),'dark','Fresh default honors approved Dark direction')
  await shot('login-dark-1440');await theme('light');await shot('login-light-1440');await theme('dark')
  await page.getByRole('button',{name:'Use demo operator'}).click()
  await page.getByRole('button',{name:'Enter workbench'}).click()
  await page.locator('.operations-hero').waitFor()
  const docs=await(await context.request.get('http://127.0.0.1:4312/api/documents')).json()
  const invoice=docs.find(doc=>doc.kind==='invoice'&&doc.filename==='INV-0004.pdf')
  assert.ok(invoice,'Preserved native synthetic invoice exists')
  for(const mode of ['dark','light']){
    await page.setViewportSize({width:1440,height:900});await theme(mode)
    for(const [route,ready]of [['overview','.operations-hero'],['queue?status=all','.queue-surface'],['intake','.upload-surface'],['vendors','.vendor-layout'],['exports','.exports-surface'],['settings','.appearance-surface'],['document/'+invoice.id,'.source-image-frame img']]){
      await goto(route,ready);await shot(route.split(/[?/]/)[0]+'-'+mode+'-1440')
    }
    checks.push(mode+': all seven production workflows, native source and desktop overflow')
    if(!captureOnly){
      await page.getByRole('tab',{name:'Details',exact:true}).click()
      await page.locator('.field-select').filter({hasText:'Issue date'}).click()
      await page.getByRole('button',{name:'Edit Issue date',exact:true}).click()
      const input=page.getByLabel('Correct value',{exact:true})
      await input.fill('2026-06-15')
      await page.locator('.edit-form textarea').fill('Synthetic local theme QA draft')
      const node=await input.elementHandle()
      const imageBefore=await page.locator('.source-image-frame img').getAttribute('src')
      const hashBefore=await page.evaluate(()=>location.hash),before=requests.length
      await theme(mode==='dark'?'light':'dark')
      assert.equal(await input.inputValue(),'2026-06-15')
      assert.equal(await page.locator('.edit-form textarea').inputValue(),'Synthetic local theme QA draft')
      assert.equal(await node.evaluate(el=>el===document.querySelector('.edit-form input')),true,'Theme preserves DOM and active draft')
      assert.equal(await page.evaluate(()=>location.hash),hashBefore)
      assert.equal(await page.locator('.source-image-frame img').getAttribute('src'),imageBefore)
      assert.equal(await page.locator('.source-image-frame img').evaluate(el=>getComputedStyle(el).filter),'none')
      assert.equal(requests.length,before,'Theme change triggers no business request')
      await theme(mode);await page.keyboard.press('Escape')
      assert.equal(await page.locator('.edit-form').count(),0)
      await page.getByRole('tab',{name:'Details',exact:true}).focus();await page.keyboard.press('ArrowRight')
      assert.equal(await page.getByRole('tab',{name:/^Findings/}).getAttribute('aria-selected'),'true')
      assert.equal(await page.getByRole('button',{name:/^Approve v/}).isDisabled(),true)
      await page.getByRole('button',{name:/Inspect line 1 evidence/}).click()
      checks.push(mode+': draft/DOM/navigation/media preserved, no business refetch, keyboard tabs and real approval barrier')
    }
    await page.setViewportSize({width:390,height:844})
    await page.getByRole('button',{name:'Document',exact:true}).click()
    await page.evaluate(()=>scrollTo(0,0));await shot('review-'+mode+'-390');await noOverflow('mobile review')
    const dock=await page.locator('.source-evidence-dock').boundingBox(),footer=await page.locator('.data-footer').boundingBox()
    assert.ok(dock&&footer&&dock.y+dock.height<=footer.y+2,'Mobile evidence stays above persistent action')
    await page.getByRole('button',{name:'Open menu',exact:true}).click()
    await page.getByRole('dialog',{name:'Workspace navigation'}).waitFor()
    await page.keyboard.press('Escape')
    assert.equal(await page.getByRole('button',{name:'Open menu',exact:true}).getAttribute('aria-expanded'),'false')
    await goto('overview','.operations-hero');await shot('overview-'+mode+'-390')
    await goto('queue?status=all','.queue-surface');await shot('queue-'+mode+'-390')
    await page.getByRole('textbox',{name:'Filter queue'}).fill('No matching synthetic vendor')
    await page.getByText('No documents match these filters',{exact:true}).waitFor()
    await theme(mode==='dark'?'light':'dark')
    assert.equal(await page.getByRole('textbox',{name:'Filter queue'}).inputValue(),'No matching synthetic vendor')
    await page.getByRole('button',{name:'Clear search',exact:true}).click();await theme(mode)
    await page.setViewportSize({width:768,height:900});await goto('intake','.upload-surface');await shot('intake-'+mode+'-768')
    await page.setViewportSize({width:1024,height:900});await goto('queue?status=all','.queue-surface');await shot('queue-'+mode+'-1024')
    checks.push(mode+': mobile reader/action/menu/search and 768/1024 layouts')
  }
  if(!captureOnly){
    await theme('light');await page.reload();await page.locator('.queue-surface').waitFor()
    assert.equal(await page.locator('html').getAttribute('data-theme'),'light')
    await theme('system');await page.emulateMedia({colorScheme:'dark'})
    await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark')
    await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light')
    await theme('dark');await page.emulateMedia({colorScheme:'light'})
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark')
    checks.push('Persisted reload, live System transitions, explicit Dark insulated from OS')
    await page.setViewportSize({width:1440,height:900})
    await page.route('**/api/vendors',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Injected synthetic local QA outage'})}))
    await page.goto('http://127.0.0.1:4312/#/vendors')
    await page.getByRole('button',{name:/Retry/}).waitFor()
    await shot('vendors-error-dark-1440');await theme('light');await shot('vendors-error-light-1440')
    await page.unroute('**/api/vendors');await page.getByRole('button',{name:/Retry/}).click();await page.locator('.vendor-layout').waitFor()
    checks.push('Explicitly injected 503: readable in both themes and retry recovers')
    const blocked=await browser.newContext({viewport:{width:390,height:844}})
    await blocked.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new Error('Synthetic denied storage')}})})
    const blockedPage=await blocked.newPage();await blockedPage.goto('http://127.0.0.1:4312');await blockedPage.getByRole('combobox',{name:'Display theme'}).selectOption('light')
    assert.equal(await blockedPage.locator('html').getAttribute('data-theme'),'light');await blocked.close()
    checks.push('Storage-denied browser still switches for the session')
    const csp=await browser.newContext()
    await csp.addInitScript(()=>{localStorage.setItem('invoicelens:theme:v1','light');new PerformanceObserver(()=>{window.firstThemePaint=document.documentElement.dataset.theme}).observe({type:'paint',buffered:true})})
    const cspPage=await csp.newPage()
    await cspPage.route('**/theme-csp-check',route=>route.fulfill({contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'"},body:'<!doctype html><html><head><link rel="stylesheet" href="/theme-base.css"><script src="/theme-init.js"></script><script>window.inlineThemeSentinel=true</script></head><body>CSP theme bootstrap check</body></html>'}))
    await cspPage.goto('http://127.0.0.1:4312/theme-csp-check')
    assert.equal(await cspPage.locator('html').getAttribute('data-theme'),'light')
    assert.equal(await cspPage.evaluate(()=>window.inlineThemeSentinel),undefined)
    assert.equal(await cspPage.evaluate(()=>getComputedStyle(document.documentElement).colorScheme),'light')
    await cspPage.waitForFunction(()=>window.firstThemePaint);assert.equal(await cspPage.evaluate(()=>window.firstThemePaint),'light')
    await csp.close();checks.push('Saved Light is applied at first paint under CSP that blocks inline scripts')
  }
  assert.deepEqual(errors,[])
  outcome='passed'
}catch(error){failure=error.message;await shot('failure-state');throw error}
finally{
  await fs.writeFile(path.join(dir,captureOnly?'capture-result.json':'qa-result.json'),JSON.stringify({outcome,checks,pageErrors:errors,failure,browser:'user local Chrome, isolated headless context',syntheticData:true,finishedAt:new Date().toISOString()},null,2))
  await browser.close()
}
