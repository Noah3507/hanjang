import {test,expect} from './fixtures'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
const root=fileURLToPath(new URL('../..',import.meta.url))
const python=process.env.PLAYWRIGHT_PYTHON||(process.platform==='win32'?`${root}/.venv/Scripts/python.exe`:'python')
test.use({httpCredentials:{username:'presenter',password:process.env.HANJANG_PRESENTATION_PASSWORD||'synthetic-ci-presentation-password'},trace:'off',video:'off'})

test('OpenAI configuration visible without any generation POST',async({page,request},info)=>{
 test.skip(process.env.PLAYWRIGHT_OPENAI_PREFLIGHT!=='1','Opt-in local preflight; never generates copy')
 const response=await request.get('/ready');expect(response.status()).toBe(200)
 expect((await response.json()).copy_provider).toBe('openai')
 let generationPosts=0
 await page.route('**/copy-generation',async route=>{
  if(route.request().method()==='POST'){generationPosts++;await route.abort();return}
  await route.continue()
 })
 await page.goto('/')
 const buffer=execFileSync(python,['-c',"from PIL import Image;import io,sys;b=io.BytesIO();Image.new('RGB',(300,300),'orange').save(b,'PNG');sys.stdout.buffer.write(b.getvalue())"])
 await page.getByLabel('상품 사진',{exact:true}).setInputFiles({name:'synthetic-preflight.png',mimeType:'image/png',buffer})
 await page.getByLabel('가게명',{exact:true}).fill('Synthetic shop')
 await page.getByLabel('상품명',{exact:true}).fill('Synthetic product')
 await page.getByLabel('가격',{exact:true}).fill('3,000 KRW')
 await page.getByLabel('광고 분위기').selectOption('warm')
 await page.getByRole('button',{name:'상품 정보와 사진 저장'}).click()
 await expect(page.getByText('OpenAI 모드 · gpt-5.4-mini-2026-03-17')).toBeVisible()
 await expect(page.getByText('카피 상태: pending')).toBeVisible()
 await expect(page.getByRole('button',{name:'4전략 카피 생성'})).toBeEnabled()
 await expect(page.getByText(/Mock 데모/)).toHaveCount(0)
 expect(generationPosts).toBe(0)
 await page.screenshot({path:info.outputPath('openai-preflight-no-dispatch.png'),fullPage:true})
})
