import {test,expect} from './fixtures'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
const root=fileURLToPath(new URL('../..',import.meta.url))
const python=process.env.PLAYWRIGHT_PYTHON||(process.platform==='win32'?`${root}/.venv/Scripts/python.exe`:'python')
test.use({httpCredentials:{username:'presenter',password:process.env.HANJANG_PRESENTATION_PASSWORD||'synthetic-ci-presentation-password'},trace:'off',video:'off'})

test('particle failure is visible without retry or paid dispatch',async({page},info)=>{
 test.skip(process.env.PLAYWRIGHT_PARTICLE_REVIEW!=='1','Explicit isolated UI check; synthetic response only')
 let intercepted=0
 await page.route('**/copy-generation',async route=>{
  if(route.request().method()!=='POST'){await route.continue();return}
  intercepted++
  await route.fulfill({status:202,json:{operation:'copy_generation',status:'failed',provider:'openai',
   model:'gpt-5.4-mini-2026-03-17',is_current:true,source_asset_id:route.request().postDataJSON().expected_asset_id,variants:[],warnings:[],attempts:[],
   error:{code:'COPY_PARTICLE_INVALID',message:'가격·상품명 뒤의 한국어 조사를 확인해야 합니다.'}}})
 })
 await page.goto('/')
 const buffer=execFileSync(python,['-c',"from PIL import Image;import io,sys;b=io.BytesIO();Image.new('RGB',(300,300),'orange').save(b,'PNG');sys.stdout.buffer.write(b.getvalue())"])
 await page.getByLabel('상품 사진',{exact:true}).setInputFiles({name:'synthetic-review.png',mimeType:'image/png',buffer})
 await page.getByLabel('가게명',{exact:true}).fill('Synthetic shop')
 await page.getByLabel('상품명',{exact:true}).fill('국수')
 await page.getByLabel('가격',{exact:true}).fill('10,500원')
 await page.getByLabel('광고 분위기').selectOption('warm')
 await page.getByRole('button',{name:'상품 정보와 사진 저장'}).click()
 await expect(page.getByRole('button',{name:'4전략 카피 생성'})).toBeEnabled()
 await page.getByRole('button',{name:'4전략 카피 생성'}).click()
 await expect(page.getByRole('alert')).toContainText('COPY_PARTICLE_INVALID')
 await expect(page.getByRole('button',{name:'광고 4장 렌더링'})).toBeDisabled()
 await expect(page.getByLabel('가격',{exact:true})).toHaveValue('10,500원')
 expect(intercepted).toBe(1)
 await page.screenshot({path:info.outputPath('particle-review-synthetic-error.png'),fullPage:true})
})
