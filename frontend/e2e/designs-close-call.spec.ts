import {test,expect,openOptional} from './fixtures'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'

test('simulated model guidance: four strategies, raw boundary, failure and stale revision',async({page})=>{
 test.setTimeout(120000)
 const root=fileURLToPath(new URL('../..',import.meta.url))
 const python=process.env.PLAYWRIGHT_PYTHON||(process.platform==='win32'?`${root}/.venv/Scripts/python.exe`:'python')
 const photo=execFileSync(python,['-c',"from PIL import Image;import io,sys;b=io.BytesIO();Image.new('RGB',(400,400),'#eee').save(b,'PNG');sys.stdout.buffer.write(b.getvalue())"])
 let mode='current',source:Record<string,unknown>
 let resolveSource:()=>void=()=>{}
 const sourceReady=new Promise<void>(resolve=>{resolveSource=resolve})
 await page.route('**/designs/**',async route=>{
  await sourceReady
  const strategy=new URL(route.request().url()).pathname.split('/designs/')[1].split('/')[0]
  const original=source.candidates as {candidate_id:string}[]
  const gap={emotional:0.1,price:0.2,visual:0.2001,brand:1}[strategy]!
  const candidates=original.map((c,i)=>({...c,strategy,template_id:strategy+'_'+'abcd'[i],design_name:'test',generation_revision:1,edit_revision:0,original_price_text:'10원'}))
  await route.fulfill({json:{...source,source_revision:source.revision,operation:'designs_v3',strategy,status:'completed',is_current:mode!=='stale',editing:false,snapshot:'a'.repeat(64),revision:1,
   candidates,diagnostics:[],ranking_status:mode==='failed'?'failed':'completed',ranking_error:mode==='failed'?{code:'SIMULATED_FAILURE',message:'테스트 모델 실패'}:null,
   ranking_close_call_score_gap:0.2,ranking:{source:'model',model_version:'synthetic-browser-fixture',revision:1,
    items:candidates.map((c,i)=>({candidate_id:c.candidate_id,rank:i+1,score:[gap,0,-1,-2][i]}))}}})
 })
 await page.goto('/')
 await page.getByLabel('상품 사진',{exact:true}).setInputFiles({name:'synthetic.png',mimeType:'image/png',buffer:photo})
 await page.getByLabel('가게명',{exact:true}).fill('테스트 상점')
 await page.getByLabel('상품명',{exact:true}).fill('테스트 상품')
 await page.getByLabel('가격',{exact:true}).fill('10원')
 await openOptional(page)
 await page.getByLabel('광고 분위기').selectOption('warm')
 await page.getByRole('button',{name:'상품 정보와 사진 저장'}).click()
 await page.getByRole('button',{name:'4전략 카피 생성'}).click()
 await expect(page.getByText('카피 상태: completed')).toBeVisible()
 const ready=page.waitForResponse(async r=>r.request().method()==='GET'&&r.url().endsWith('/rendering')&&(await r.json()).status==='completed')
 await page.getByRole('button',{name:'광고 4장 렌더링'}).click()
 source=await (await ready).json()
 resolveSource()
 const region=page.getByRole('region',{name:'전략별 디자인 4종'})
 for(const [label,s,close] of [['감성','emotional',true],['가격','price',true],['비주얼','visual',false],['브랜드','brand',false]] as const){
  await region.getByRole('button',{name:label+' 전략 선택',exact:true}).click()
  await expect(region.getByRole('article',{name:s+'_a 시안'})).toBeVisible()
  await expect(region.getByRole('note')).toHaveCount(close?1:0)
 }
 await region.getByRole('button',{name:'가격 전략 선택',exact:true}).click()
 await expect(region.getByRole('note')).toHaveCount(1)
 mode='failed';await region.getByRole('button',{name:'결과 다시 불러오기',exact:true}).click()
 await expect(region.getByText('테스트 모델 실패')).toBeVisible()
 await expect(region.getByRole('note')).toHaveCount(0)
 mode='stale';await region.getByRole('button',{name:'결과 다시 불러오기',exact:true}).click()
 await expect(region.getByText('이전 입력의 시안입니다. 최신 결과로 다시 생성해 주세요.')).toBeVisible()
 await expect(region.getByRole('note')).toHaveCount(0)
 await expect(region.getByText(/추천 점수/)).toHaveCount(0)
})
