import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const source = fs.readFileSync(new URL('../public/theme-init.js', import.meta.url), 'utf8')
function boot({ saved = null, osDark = false, blocked = false } = {}) {
  const data = {}, handlers = new Set(), events = {}, writes = []
  const media = { matches: osDark, addEventListener: (_, fn) => handlers.add(fn), removeEventListener: (_, fn) => handlers.delete(fn) }
  const window = { matchMedia: () => media, localStorage: { getItem: () => { if (blocked) throw Error('blocked'); return saved }, setItem: (key, value) => { if (blocked) throw Error('blocked'); writes.push([key, value]) } }, addEventListener: (event, fn) => { events[event] = fn } }
  vm.runInNewContext(source, { window, document: { documentElement: { dataset: data }, querySelector: () => null } })
  return { store: window.invoiceLensTheme, data, media, handlers, events, writes }
}
test('pre-paint defaults to dark, rejects corruption and preserves valid preferences', () => {
  assert.equal(boot().data.theme, 'dark'); assert.equal(boot({ saved: 'broken' }).data.theme, 'dark')
  assert.equal(boot({ saved: 'light', osDark: true }).data.theme, 'light')
  assert.equal(boot({ saved: 'system', osDark: false }).data.theme, 'light')
})
test('only System watches OS changes; explicit preference stops following the OS', () => {
  const { store, media, handlers, writes } = boot()
  let changes = 0; const unsubscribe = store.subscribe(() => changes++)
  store.setPreference('system'); assert.equal(handlers.size, 1)
  media.matches = true; handlers.forEach(fn => fn()); assert.equal(store.getSnapshot().resolved, 'dark')
  store.setPreference('light'); assert.equal(handlers.size, 0)
  assert.equal(store.getSnapshot().resolved, 'light'); assert.equal(changes, 3)
  unsubscribe(); store.setPreference('dark'); assert.equal(changes, 3)
  assert.deepEqual(writes.at(-1), ['invoicelens:theme:v1', 'dark'])
})
test('unavailable storage still applies a session preference without throwing', () => {
  const { store, data } = boot({ blocked: true }); store.setPreference('light')
  assert.equal(data.theme, 'light'); assert.equal(store.getSnapshot().storageAvailable, false)
})
test('cross-tab input is validated; stable snapshots avoid unrelated renders', () => {
  const { store, events } = boot({ saved: 'light' })
  const snapshot = store.getSnapshot(); store.setPreference('light'); assert.equal(store.getSnapshot(), snapshot)
  events.storage({ key: 'unrelated', newValue: 'dark' }); assert.equal(store.getSnapshot(), snapshot)
  events.storage({ key: 'invoicelens:theme:v1', newValue: 'system' }); assert.equal(store.getSnapshot().preference, 'system')
  store.setPreference('invalid'); assert.equal(store.getSnapshot().preference, 'system')
})
test('core text, subtle labels and primary controls meet 4.5:1 in both semantic palettes', () => {
  const css=fs.readFileSync(new URL('../public/theme-base.css',import.meta.url),'utf8')
  const [dark,light]=css.split(':root[data-theme="light"] {')
  const luminance=hex=>{
    if(hex.length===4) hex='#'+[...hex.slice(1)].map(value=>value+value).join('')
    const values=[1,3,5].map(start=>parseInt(hex.slice(start,start+2),16)/255).map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4)
    return values[0]*.2126+values[1]*.7152+values[2]*.0722
  }
  for(const palette of [dark,light.slice(0,light.indexOf('}'))]){
    const tokens=Object.fromEntries([...palette.matchAll(/(--il-[\w-]+):(#[\da-f]{6}|#[\da-f]{3})\b/gi)].map(match=>[match[1],match[2]]))
    const pairs=['surface','raised','inset','inspector'].flatMap(background=>['ink','muted','faint'].map(foreground=>[foreground,background]))
    pairs.push(['accent','accent-soft'],['accent-ink','accent'],['success','success-soft'],['warning','warning-soft'],['danger','danger-soft'],['chart-axis','chart-tooltip'])
    for(const [foreground,background]of pairs){
      const values=[luminance(tokens['--il-'+foreground]),luminance(tokens['--il-'+background])].sort((a,b)=>b-a)
      assert.ok((values[0]+.05)/(values[1]+.05)>=4.5,foreground+' on '+background)
    }
  }
})
