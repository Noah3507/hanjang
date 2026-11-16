// Trusted escaped HTML only. Network, page scripts and external fonts are blocked.
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
let input = ''; for await (const part of process.stdin) input += part
let browser
try {
  const task = JSON.parse(input)
  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1080, height: 1350 },
    deviceScaleFactor: 1, javaScriptEnabled: false, serviceWorkers: 'block' })
  await context.route('**/*', route => route.abort())
  const results = []
  for (const item of task.pages) {
    const page = await context.newPage()
    try {
      await page.setContent(item.html, { waitUntil: 'load' })
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode())) })
      const measurement = await page.evaluate(() => {
        const box = e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height } }
        const steps = []
        const text = [...document.querySelectorAll('[data-field]')].filter(e => e.textContent.length).map(e => {
          const initial = getComputedStyle(e), size = parseFloat(initial.fontSize)
          const fits = () => {
            const r = document.createRange(); r.selectNodeContents(e)
            const b = r.getBoundingClientRect(), slot = e.getBoundingClientRect()
            return b.width <= slot.width + 1 && b.height <= slot.height + 1 &&
              e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1
          }
          // Slot sizes and photo geometry stay fixed; natural wrapping comes first.
          let fit = fits(), stage = 'natural-wrap'
          if (!fit) { e.style.letterSpacing = '-.035em'; e.style.lineHeight = '1.15'; fit = fits(); stage = 'spacing' }
          for (const scale of [.94, .88, .82, .76]) {
            if (fit) break
            e.style.fontSize = `${Math.max(e.dataset.field === 'price_text' ? 42 : 22, size * scale)}px`
            fit = fits(); stage = `size-${scale}`
          }
          const s = getComputedStyle(e), r = document.createRange(); r.selectNodeContents(e)
          const rects = [...r.getClientRects()].map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height }))
          steps.push({ field: e.dataset.field, stage, fits: fit })
          return { ...box(e), field: e.dataset.field, text: e.textContent, font_size_px: parseFloat(s.fontSize),
            font_weight: Number(s.fontWeight), font_family: s.fontFamily, foreground: s.color, background: s.backgroundColor,
            letter_spacing: s.letterSpacing, line_height: s.lineHeight, line_count: new Set(rects.map(r => Math.round(r.y))).size,
            glyph_rects: rects, overflow: !fit, contrast_eligible: !e.closest('.stamp') && !e.closest('.badge') && !e.closest('header'),
            visible: !!e.getClientRects().length }
        })
        const overlap = (a, b) => Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>1 && Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>1
        const collisions = text.flatMap((a,i) => text.slice(i+1).filter(b => overlap(a,b)).map(b => [a.field,b.field]))
        const outside = text.some(t => t.x < 0 || t.y < 0 || t.x+t.width > 1080.1 || t.y+t.height > 1350.1)
        const photo=box(document.querySelector('.photo'))
        return { text, product: photo, photo_frame: photo,
          layout: 'fixed-slots-v3', image_fit: getComputedStyle(document.querySelector('.photo img')).objectFit, fit_steps: steps, text_collisions: collisions,
          intentional_image_overlays: text.filter(t=>overlap(t,photo)).map(t=>({field:t.field,classification:'template-overlay-needs-review'})),
          decorative_text: [...document.querySelectorAll('[data-decoration]')].map(e=>({kind:e.dataset.decoration,bbox:box(e),text:e.textContent,excluded_from_reading_order:true})),
          invalid: outside || collisions.length > 0 || text.some(t => t.overflow || !t.visible) }
      })
      measurement.template_id = item.template_id
      if (measurement.invalid) {
        const error = new Error('RENDER_LAYOUT_OVERFLOW'); error.measurement = measurement; throw error
      }
      const cdp = await context.newCDPSession(page)
      await cdp.send('DOM.enable'); await cdp.send('CSS.enable')
      const {root} = await cdp.send('DOM.getDocument')
      const {nodeIds} = await cdp.send('DOM.querySelectorAll', {nodeId:root.nodeId,selector:'[data-field]'})
      for (const nodeId of nodeIds) {
        const {fonts} = await cdp.send('CSS.getPlatformFontsForNode',{nodeId})
        if (fonts.some(f=>!f.isCustomFont)) throw Error('RENDER_UNSUPPORTED_GLYPH')
        // Attach by field, including optional empty nodes skipped above.
        const {attributes} = await cdp.send('DOM.getAttributes',{nodeId})
        const index = attributes.indexOf('data-field')
        const row = measurement.text.find(t=>t.field===attributes[index+1])
        if (row) { row.actual_fonts = fonts; if (!fonts.length) throw Error('RENDER_FONT_UNAVAILABLE') }
      }
      await cdp.detach()
      const png = (await page.screenshot({type:'png'})).toString('base64')
      await page.evaluate(()=>{for (const e of document.querySelectorAll('.text')) e.style.setProperty('-webkit-text-fill-color','transparent','important')})
      const background_png = (await page.screenshot({type:'png'})).toString('base64')
      results.push({template_id:item.template_id,png,background_png,measurement})
    } finally { await page.close() }
  }
  process.stdout.write(JSON.stringify({results}))
} catch (e) {
  process.stdout.write(JSON.stringify({error:['RENDER_LAYOUT_OVERFLOW','RENDER_UNSUPPORTED_GLYPH','RENDER_FONT_UNAVAILABLE'].includes(e.message)?e.message:'RENDER_FAILED',measurement:e.measurement}))
  process.exitCode=1
} finally { if (browser) await browser.close() }
