// Trusted raster-only A4 composition. No user HTML, file paths, scripts or network.
import { chromium } from '../frontend/node_modules/playwright/index.mjs'
let input='';for await(const part of process.stdin)input+=part
let browser
try {
 const task=JSON.parse(input)
 if(typeof task.png!=='string'||!/^[-A-Za-z0-9+/=]+$/.test(task.png))throw Error('invalid image')
 browser=await chromium.launch({headless:true,...(process.env.HANJANG_RENDER_CHANNEL?{channel:process.env.HANJANG_RENDER_CHANNEL}:{})})
 const context=await browser.newContext({javaScriptEnabled:false,serviceWorkers:'block'})
 await context.route('**/*',r=>r.abort())
 const page=await context.newPage()
 // Whole CSS pixels in a 4:5 ratio avoid Chromium's asymmetric print rounding.
 // 716x895 CSS px = about 189.44x236.80mm, centered with >10mm margins.
 await page.setContent(`<meta http-equiv="Content-Security-Policy" content="default-src 'none';img-src data:;style-src 'unsafe-inline'"><style>@page{size:210mm 297mm;margin:0}*{box-sizing:border-box}html,body{margin:0;width:210mm;height:297mm;background:white}img{position:absolute;left:calc((210mm - 716px)/2);top:calc((297mm - 895px)/2);width:716px;height:895px;object-fit:contain}</style><img src="data:image/png;base64,${task.png}">`)
 await page.evaluate(async()=>Promise.all([...document.images].map(i=>i.decode())))
 const bounds=await page.locator('img').boundingBox()
 const pdf=await page.pdf({preferCSSPageSize:true,printBackground:true,margin:{top:0,bottom:0,left:0,right:0},tagged:false})
 process.stdout.write(JSON.stringify({pdf:pdf.toString('base64'),bounds}))
 await context.close()
}catch{process.stdout.write(JSON.stringify({error:'PDF_FAILED'}));process.exitCode=1}
finally{if(browser)await browser.close()}
