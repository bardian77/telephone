// Screenshots of the built site, and a check that it works: every page loads without an error,
// "Pass it on" steps through the passes, and "try your own photo" finishes on a real file.
//
//   cd web && npm run build
//   python ../.claude/skills/webapp-testing/scripts/with_server.py \
//     --server "npm run preview -- --port 4173 --strictPort" --port 4173 \
//     -- node scripts/screenshots.cjs ../docs/tutorial-17nov/site
//
// The photo used for "try your own photo" is one of my own originals. It is read by the browser
// on this machine, like any visitor's would be, and goes nowhere.
const path = require('path')
const fs = require('fs')
const { chromium, devices } = require('playwright')

const base = process.env.SITE_URL || 'http://localhost:4173'
const out = path.resolve(process.argv[2] || '../docs/tutorial-17nov/site')
const myPhoto = path.resolve(__dirname, '../../data/originals/street_barbican_lake_01.jpg')
const problems = []

async function open(context, hash) {
  const page = await context.newPage()
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`${hash}: console: ${m.text()}`) })
  page.on('pageerror', (e) => problems.push(`${hash}: ${e.message}`))
  await page.goto(`${base}/#${hash}`)
  await page.waitForLoadState('networkidle')
  return page
}

async function main() {
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch()

  // a laptop
  const desktop = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 2 })
  let page = await open(desktop, '/')
  await page.screenshot({ path: path.join(out, 'home-desktop-original.png') })
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Pass it on' }).click()
  const tag = await page.locator('.stage .tag').first().textContent()
  if (!/Pass 5 of/.test(tag || '')) problems.push(`after three presses the page shows "${tag}", not pass 5`)
  await page.screenshot({ path: path.join(out, 'home-desktop-pass5.png') })
  await page.getByRole('group', { name: 'Go to a pass' }).getByRole('button', { name: '40', exact: true }).click()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: path.join(out, 'home-desktop-pass40.png') })
  await page.screenshot({ path: path.join(out, 'home-desktop-pass40-full.png'), fullPage: true })

  // each journey and each photograph can be chosen, and none leaves the page without a picture
  for (const label of ['Upload it again', 'Screenshot it, then upload', 'A careless crop every time', 'A different phone every time']) {
    await page.getByText(label, { exact: true }).click()
    if (!(await page.locator('.stage img').first().isVisible())) problems.push(`no picture after choosing "${label}"`)
  }
  const pick = page.locator('.picker button')
  for (let i = 0; i < (await pick.count()); i++) {
    await pick.nth(i).click()
    const ok = await page
      .waitForFunction(() => { const img = document.querySelector('.stage img'); return img && img.complete && img.naturalWidth > 0 }, null, { timeout: 15000 })
      .then(() => true, () => false)
    if (!ok) problems.push(`photograph ${i + 1} did not load`)
  }

  // try your own photo, with one of my own
  await page.setInputFiles('input[type=file]', myPhoto)
  await page.getByText('Done: 20 passes.').waitFor({ timeout: 120000 })
  await page.locator('.try').scrollIntoViewIfNeeded()
  await page.locator('.try').screenshot({ path: path.join(out, 'try-your-own-desktop.png') })
  await page.close()

  for (const [hash, name] of [['/how', 'how-desktop'], ['/about', 'about-desktop']]) {
    page = await open(desktop, hash)
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true })
    await page.close()
  }
  await desktop.close()

  // a phone
  const phone = await browser.newContext({ ...devices['iPhone 13'] })
  page = await open(phone, '/')
  await page.screenshot({ path: path.join(out, 'home-phone-original.png') })
  await page.getByRole('button', { name: 'Pass it on' }).click()
  await page.getByRole('button', { name: 'Pass it on' }).click()
  await page.screenshot({ path: path.join(out, 'home-phone-full.png'), fullPage: true })
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  if (sideways) problems.push('the page scrolls sideways on a phone')
  await page.close()
  page = await open(phone, '/how')
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)) problems.push('How it works scrolls sideways on a phone')
  await page.screenshot({ path: path.join(out, 'how-phone.png'), fullPage: true })
  await phone.close()

  // with motion turned down the picture must not animate
  const calm = await browser.newContext({ viewport: { width: 1366, height: 900 }, reducedMotion: 'reduce' })
  page = await open(calm, '/')
  const animation = await page.locator('.stage img').first().evaluate((img) => getComputedStyle(img).animationName)
  if (animation !== 'none') problems.push(`the picture still animates with reduced motion (${animation})`)
  await calm.close()

  await browser.close()
  if (problems.length) {
    console.error(problems.join('\n'))
    process.exit(1)
  }
  console.log(`screenshots written to ${out}; no problems found`)
}

main().catch((e) => { console.error(e); process.exit(1) })
