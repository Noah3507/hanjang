import {test,expect,openOptional} from './fixtures'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {readFile,writeFile} from 'node:fs/promises'
const root=fileURLToPath(new URL('../..',import.meta.url))
const python=process.env.PLAYWRIGHT_PYTHON||(process.platform==='win32'?`${root}/.venv/Scripts/python.exe`:'python')

test('v2 to strategy variants, model and diagnostics, edit, downloads and restore',async({page},info)=>{
 test.setTimeout(240000)
 page.setDefaultTimeout(15000)
 let paid=0
 page.on('request',r=>{if(r.url().includes('api.openai.com'))paid++})
 await page.goto('/')
 const realPhoto=process.env.PLAYWRIGHT_V3_PHOTO
 const product=realPhoto?'아부라소바':'데일리 로션'
 const editedHeadline='새롭게 만나는 '+product
 const image=realPhoto?await readFile(realPhoto):execFileSync(python,['-c',"from PIL import Image;import io,sys;s=io.BytesIO();Image.new('RGB',(600,800),'#b7bca8').save(s,'PNG');sys.stdout.buffer.write(s.getvalue())"])
 await page.getByLabel('상품 사진',{exact:true}).setInputFiles({name:'v3.png',mimeType:'image/png',buffer:image})
 await page.getByLabel('가게명',{exact:true}).fill(realPhoto?'쿠지라스토랑':'한장 상점')
 await page.getByLabel('상품명',{exact:true}).fill(product)
 await page.getByLabel('가격',{exact:true}).fill('10,500원')
 await openOptional(page)
 await page.getByLabel('광고 분위기').selectOption('warm')
 await page.getByRole('button',{name:'상품 정보와 사진 저장'}).click()
 await page.getByRole('button',{name:'4전략 카피 생성'}).click()
 await expect(page.getByText('카피 상태: completed')).toBeVisible()
 await page.getByRole('button',{name:'광고 4장 렌더링'}).click()
 await expect(page.getByText('렌더링 상태: completed')).toBeVisible({timeout:60000})
 await page.getByRole('button',{name:'가격 디자인 전략으로 선택'}).click()
 const region=page.getByRole('region',{name:'전략별 디자인 4종'})
 await region.getByRole('button',{name:'이 전략으로 시안 4개 더 보기'}).click()
 await expect(region.getByText('시안 상태: completed · revision 1',{exact:true})).toBeVisible({timeout:60000})
 await expect(region.getByRole('article')).toHaveCount(4)
 const rankResponse=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/designs/price/ranking'))
 await region.getByRole('button',{name:'시안 ML 참고 순위 계산'}).click()
 const ranked=await (await rankResponse).json()
 await writeFile(info.outputPath('ranking-evidence.json'),JSON.stringify({source:ranked.ranking?.source,model_version:ranked.ranking?.model_version,items:ranked.ranking?.items,error:ranked.ranking_error},null,2))
 if(process.env.PLAYWRIGHT_REQUIRE_RANKING_MODEL==='1'){
  await expect(region.getByText(/bt-logistic-v1/)).toHaveCount(4,{timeout:60000})
  const gap=ranked.ranking_close_call_score_gap
  expect(typeof gap).toBe('number')
  const items=[...ranked.ranking.items].sort((a,b)=>a.rank-b.rank)
  await expect(region.getByRole('note')).toHaveCount(items[0].score-items[1].score<=gap?1:0)
 }
 else await expect(region.getByText('시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다.')).toBeVisible()
 await expect(region.getByRole('article').locator('details')).toHaveCount(4)
 await region.getByRole('button',{name:'시안 A 편집',exact:true}).click()
 await region.getByLabel('v3 제목',{exact:true}).fill(editedHeadline)
 await region.getByRole('button',{name:'시안 적용하고 재렌더링'}).click()
 await expect(region.getByText('시안 상태: completed · revision 2',{exact:true})).toBeVisible({timeout:60000})
 await expect(region.getByRole('article').first()).toContainText(editedHeadline)
 await region.getByRole('button',{name:'시안 B 편집',exact:true}).click()
 await region.getByLabel('v3 가격',{exact:true}).fill('12,000원')
 await region.getByRole('button',{name:'시안 적용하고 재렌더링'}).click()
 await expect(region.getByText('시안 상태: completed · revision 3',{exact:true})).toBeVisible({timeout:60000})
 await expect(region.getByRole('article').nth(1)).toContainText('12,000원')
 for(const format of ['png','pdf'] as const){
  const event=page.waitForEvent('download');await region.getByRole('article').first().getByRole('button',{name:format==='png'?'시안 PNG 다운로드':'시안 PDF 다운로드'}).click()
  const file=await event;await file.saveAs(info.outputPath(`v3-edited.${format}`));const data=await readFile(info.outputPath(`v3-edited.${format}`))
  if(format==='png'){expect(data.readUInt32BE(16)).toBe(1080);expect(data.readUInt32BE(20)).toBe(1350)}
  else{expect(data.subarray(0,5).toString()).toBe('%PDF-');expect(data.toString('latin1').match(/\/Type\s*\/Page\b/g)).toHaveLength(1)}
 }
 await region.getByRole('button',{name:'감성 전략 선택',exact:true}).click()
 await region.getByRole('button',{name:'이 전략으로 시안 4개 더 보기'}).click()
 await expect(region.getByRole('article',{name:'emotional_a 시안'})).toBeVisible({timeout:60000})
 await region.getByRole('button',{name:'가격 전략 선택',exact:true}).click()
 await expect(region.getByText('시안 상태: completed · revision 3',{exact:true})).toBeVisible()
 await region.getByRole('button',{name:'시안 A 편집',exact:true}).click()
 await region.getByLabel('v3 제목',{exact:true}).fill('취소할 문구')
 await region.getByRole('button',{name:'시안 편집 취소'}).click()
 await expect(region.getByRole('button',{name:'시안 A 편집',exact:true})).toBeFocused()
 await expect(region.getByText(editedHeadline,{exact:true})).toBeVisible()
 await page.reload();await page.getByRole('button',{name:'저장 정보 다시 조회'}).click()
 await expect(region.getByText('시안 상태: completed · revision 3',{exact:true})).toBeVisible({timeout:30000})
 const v2=page.getByRole('region',{name:'광고 편집 및 다운로드'})
 await expect(v2.getByRole('heading')).toContainText('revision 1')
 const event=page.waitForEvent('download');await v2.getByRole('button',{name:'PNG 다운로드',exact:true}).click();await (await event).saveAs(info.outputPath('v2-preserved.png'))
 await page.screenshot({path:info.outputPath('v3-desktop.png'),fullPage:true})
 await page.setViewportSize({width:375,height:900});await expect(page.locator('body')).toHaveJSProperty('scrollWidth',375)
 await page.screenshot({path:info.outputPath('v3-mobile.png'),fullPage:true})
 expect(paid).toBe(0)
})
