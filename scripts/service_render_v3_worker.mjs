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
      if (await page.evaluate(() => [...document.fonts].some(f => f.status === 'error'))) throw Error('RENDER_FONT_UNAVAILABLE')
      const placement=task.photo_info?await page.evaluate(info=>{
        const frame=document.querySelector('.photo'),img=frame.querySelector('img'),style=getComputedStyle(frame)
        const w=frame.clientWidth,h=frame.clientHeight,pw=img.naturalWidth,ph=img.naturalHeight
        const tid=document.querySelector('.ad').classList[1]
        const circle=['price_a','price_c','emotional_d','brand_a','brand_b'].includes(tid)&&!frame.classList.contains('whole-photo')
        const full=['emotional_b','visual_a','visual_c','visual_d'].includes(tid)
        const inset=circle?Math.max(10,Math.min(w,h)*.035):full?8:Math.max(12,Math.min(w,h)*.025)
        const b=info.support_in_prepared||[0,0,pw,ph],cx=(b[0]+b[2])/2,cy=(b[1]+b[3])/2
        let scale=Math.min((w-2*inset)/pw,(h-2*inset)/ph)
        let norm=0
        if(circle){
          const rx=w/2-inset,ry=h/2-inset
          const add=(x,y)=>{norm=Math.max(norm,((x-cx)/rx)**2+((y-cy)/ry)**2)}
          if(info.support_rows?.length){for(const [y,l,r] of info.support_rows){for(const x of [l,r]){add(x,y);add(x,y+1)}}}
          else for(const x of [0,pw])for(const y of [0,ph])add(x,y)
          scale=Math.min(scale,.985/Math.sqrt(norm||1))
        }
        const left=w/2-cx*scale,top=h/2-cy*scale
        Object.assign(img.style,{position:'absolute',width:`${pw*scale}px`,height:`${ph*scale}px`,left:`${left}px`,top:`${top}px`,padding:'0',maxWidth:'none',maxHeight:'none',objectFit:'contain'})
        const fr=frame.getBoundingClientRect(),borderL=parseFloat(style.borderLeftWidth),borderT=parseFloat(style.borderTopWidth)
        const bbox={x:fr.x+borderL+left+b[0]*scale,y:fr.y+borderT+top+b[1]*scale,width:(b[2]-b[0])*scale,height:(b[3]-b[1])*scale}
        const clipped=circle?norm*scale*scale>1.00001:left+b[0]*scale<0||top+b[1]*scale<0||left+b[2]*scale>w+.01||top+b[3]*scale>h+.01
        const decorativeOcclusions=[...document.querySelectorAll('.decoration')].filter(e=>Number(getComputedStyle(e).zIndex)>0).map(e=>{
          const r=e.getBoundingClientRect();return {kind:'intentional-front-gradient',x:r.x,y:r.y,width:r.width,height:r.height}
        }).filter(r=>Math.min(r.x+r.width,bbox.x+bbox.width)>Math.max(r.x,bbox.x)&&Math.min(r.y+r.height,bbox.y+bbox.height)>Math.max(r.y,bbox.y))
        return {policy:circle?'alpha-ellipse-safe':full?'full-frame-safe':'rectangle-safe',subject_known:info.subject_detection==='alpha-support',
          source:info.subject_detection,scale,subject_bbox:bbox,subject_linear_occupancy:Math.max(bbox.width/w,bbox.height/h),
          unintended_clip:clipped,discarded_low_alpha_mass_ratio:info.discarded_low_alpha_mass_ratio,canvas_padding_px:inset,
          decorative_occlusions:decorativeOcclusions,preparation:Object.fromEntries(Object.entries(info).filter(([k])=>k!=='support_rows'))}
      },task.photo_info):null
      const measurement = await page.evaluate(usePriority => {
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
          if (!fit) { e.style.setProperty('letter-spacing','-.035em',usePriority?'important':''); e.style.setProperty('line-height','1.15',usePriority?'important':''); fit = fits(); stage = 'spacing' }
          for (const scale of [.94, .88, .82, .76]) {
            if (fit) break
            e.style.setProperty('font-size',`${Math.max(e.dataset.field === 'price_text' ? 42 : 22, size * scale)}px`,usePriority?'important':'')
            fit = fits(); stage = `size-${scale}`
          }
          const s = getComputedStyle(e), r = document.createRange(); r.selectNodeContents(e)
          const rects = [...r.getClientRects()].map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height }))
          steps.push({ field: e.dataset.field, stage, fits: fit, initial_font_size_px:size,
            final_font_size_px:parseFloat(s.fontSize), size_ratio:parseFloat(s.fontSize)/size })
          return { ...box(e), field: e.dataset.field, text: e.textContent, font_size_px: parseFloat(s.fontSize),
            initial_font_size_px:size, size_ratio:parseFloat(s.fontSize)/size,
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
      },Boolean(task.photo_info))
      measurement.template_id = item.template_id
      if(placement){measurement.image_placement=placement;measurement.product=placement.subject_bbox}
      if (measurement.invalid) {
        const error = new Error('RENDER_LAYOUT_OVERFLOW'); error.measurement = measurement; throw error
      }
      const background=task.backgrounds?.[item.template_id]
      if(background){
        if(placement?.decorative_occlusions?.length)throw Error('BACKGROUND_FOREGROUND_OVERLAY')
        measurement.background_composition=await page.evaluate(async ({bg,measurement})=>{
          const image=new Image();image.src='data:image/png;base64,'+bg.png_base64;await image.decode()
          const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1350
          const ctx=canvas.getContext('2d'),p=measurement.product
          const scale=Math.max(1080/image.width,1350/image.height),sw=image.width*scale,sh=image.height*scale
          const directed=bg.policy==='directed'
          // Align the plate's reviewed quiet centre with the actual product.
          const ox=directed?Math.max(0,Math.min(sw-1080,sw*.5-(p.x+p.width/2))):(sw-1080)/2
          const oy=directed?Math.max(0,Math.min(sh-1350,sh*.42-(p.y+p.height/2))):(sh-1350)/2
          ctx.drawImage(image,-ox,-oy,sw,sh)
          const bands=[]
          if(directed){
            const boxes=measurement.text.map(t=>({top:Math.max(0,t.y-28),bottom:Math.min(1350,t.y+t.height+28)})).sort((a,b)=>a.top-b.top)
            for(const b of boxes){const last=bands.at(-1);if(last&&b.top-last.bottom<70)last.bottom=Math.max(last.bottom,b.bottom);else bands.push({...b})}
            // Quiet texture, not solid template-colour bands. Preserve the
            // photographic plate's tone; foreground colours stay B-owned.
            const soft=document.createElement('canvas');soft.width=1080;soft.height=1350
            const softContext=soft.getContext('2d');softContext.filter='blur(14px)';softContext.drawImage(canvas,0,0)
            // Background-only treatment, clipped out of the photo protection
            // rectangle. Never an overlay on the product or modified typography.
            ctx.save();ctx.beginPath();ctx.rect(0,0,1080,1350);ctx.rect(p.x-8,p.y-8,p.width+16,p.height+16);ctx.clip('evenodd')
            for(const b of bands){
              const layer=document.createElement('canvas');layer.width=1080;layer.height=1350
              const lc=layer.getContext('2d');lc.drawImage(soft,0,0);lc.globalCompositeOperation='destination-in'
              const gradient=lc.createLinearGradient(0,b.top,0,b.bottom)
              gradient.addColorStop(0,'rgba(0,0,0,0)');gradient.addColorStop(.18,'black');gradient.addColorStop(.82,'black');gradient.addColorStop(1,'rgba(0,0,0,0)')
              lc.fillStyle=gradient;lc.fillRect(0,0,1080,1350);ctx.drawImage(layer,0,0)
            }
            ctx.restore()
          }
          document.querySelector('.ad').style.backgroundImage=`url(${canvas.toDataURL('image/png')})`
          document.querySelector('.ad').style.backgroundSize='100% 100%'
          return {asset_id:bg.asset_id,sha256:bg.sha256,model:bg.model,prompt_version:bg.prompt_version,version:bg.version,policy:bg.policy,
            source_size:[image.width,image.height],offset:[ox,oy],scale,quiet_bands:bands,
            protected_product:p,contact_estimate:{x:p.x+p.width/2,y:p.y+p.height,confirmed:false},
            note:'Background layer only; existing template shadow unchanged; contact plane/light are unverified'}
        },{bg:background,measurement})
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
