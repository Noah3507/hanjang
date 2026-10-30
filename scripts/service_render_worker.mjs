// Trusted HTML only. User text is escaped by Jinja2; no page script or network.
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
let input=''; for await(const part of process.stdin) input+=part
let browser
try {
  const task=JSON.parse(input)
  browser=await chromium.launch({headless:true,...(process.env.HANJANG_RENDER_CHANNEL ? {channel:process.env.HANJANG_RENDER_CHANNEL}: {})})
  const context=await browser.newContext({viewport:{width:1080,height:1350},deviceScaleFactor:1,serviceWorkers:'block',javaScriptEnabled:false})
  await context.route('**/*',route=>route.abort())
  const results=[]
  for(const item of task.pages){
    const page=await context.newPage()
    try {
      await page.setContent(item.html,{waitUntil:'load',timeout:15000})
      await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))})
      const fontOK=await page.evaluate(()=>document.fonts.check('32px HanjangNoto') && document.fonts.size===1)
      if(!fontOK) throw Error('RENDER_FONT_UNAVAILABLE')
      let measurement
      for(const variant of ['', 'compact', 'dense']){
        measurement=await page.evaluate(variant=>{
          const root=document.querySelector('.ad');root.classList.remove('compact','dense');if(variant) root.classList.add(variant)
          const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}
          const text=[...document.querySelectorAll('[data-field]')].map(e=>{
            const s=getComputedStyle(e),r=box(e);const range=document.createRange();range.selectNodeContents(e)
            const lines=[...new Set([...range.getClientRects()].map(r=>Math.round(r.y)))].length
            return {...r,field:e.dataset.field,text:e.textContent,font_size_px:parseFloat(s.fontSize),font_weight:parseInt(s.fontWeight),
              foreground:s.color,background:s.backgroundColor,overflow:e.scrollHeight>e.clientHeight+1||e.scrollWidth>e.clientWidth+1,
              font_family:s.fontFamily,line_count:lines}
          })
          const img=document.querySelector('img'),outer=box(img),scale=Math.min(outer.width/img.naturalWidth,outer.height/img.naturalHeight)
          const product={x:outer.x+(outer.width-img.naturalWidth*scale)/2,y:outer.y+(outer.height-img.naturalHeight*scale)/2,width:img.naturalWidth*scale,height:img.naturalHeight*scale}
          const all=[...text,box(document.querySelector('.photo'))]
          const overlap=(a,b)=>Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>1&&Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>1
          const invalid=all.some(b=>b.x<53||b.y<53||b.x+b.width>1027||b.y+b.height>1297)||text.some(t=>t.overflow)||all.some((a,i)=>all.slice(i+1).some(b=>overlap(a,b)))
          return {text,product,layout:variant||'normal',invalid,photo_frame:box(document.querySelector('.photo'))}
        },variant)
        if(!measurement.invalid) break
      }
      if(measurement.invalid) { const error=Error('RENDER_LAYOUT_OVERFLOW'); error.measurement=measurement; throw error }
      // Chromium reports actually used fonts, rather than inferred CSS family.
      const cdp=await context.newCDPSession(page)
      await cdp.send('DOM.enable'); await cdp.send('CSS.enable')
      const {root}=await cdp.send('DOM.getDocument')
      const {nodeIds}=await cdp.send('DOM.querySelectorAll',{nodeId:root.nodeId,selector:'[data-field]'})
      for(let i=0;i<nodeIds.length;i++){
        const {fonts}=await cdp.send('CSS.getPlatformFontsForNode',{nodeId:nodeIds[i]})
        measurement.text[i].actual_fonts=fonts
        if(fonts.some(f=>!f.isCustomFont)) throw Error('RENDER_UNSUPPORTED_GLYPH')
      }
      await cdp.detach()
      results.push({strategy:item.strategy,measurement,png:(await page.screenshot({type:'png',animations:'disabled'})).toString('base64')})
    } finally {await page.close()}
  }
  await context.close()
  process.stdout.write(JSON.stringify({results}))
} catch(e){process.stdout.write(JSON.stringify({error:['RENDER_LAYOUT_OVERFLOW','RENDER_FONT_UNAVAILABLE','RENDER_UNSUPPORTED_GLYPH'].includes(e.message)?e.message:'RENDER_FAILED',measurement:e.measurement}));process.exitCode=1}
finally {if(browser) await browser.close()}
