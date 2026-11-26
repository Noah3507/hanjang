import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { test, expect } from './fixtures'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.env.PLAYWRIGHT_PYTHON || (process.platform === 'win32' ? `${root}/.venv/Scripts/python.exe` : 'python')

test('one click makes four designs of the chosen strategy and ranks them', async ({ page }) => {
  test.setTimeout(240_000)
  page.setDefaultTimeout(15_000)
  let paid = 0
  page.on('request', (request) => { if (request.url().includes('api.openai.com')) paid++ })
  await page.goto('/')
  const image = execFileSync(python, ['-c', "from PIL import Image;import io,sys;s=io.BytesIO();Image.new('RGB',(600,800),'#b7bca8').save(s,'PNG');sys.stdout.buffer.write(s.getvalue())"])
  await page.getByLabel('상품 사진', { exact: true }).setInputFiles({ name: 'auto.png', mimeType: 'image/png', buffer: image })
  await page.getByLabel('가게명', { exact: true }).fill('한장 상점')
  await page.getByLabel('상품명', { exact: true }).fill('데일리 로션')
  await page.getByLabel('가격', { exact: true }).fill('10,500원')
  await page.getByRole('radio', { name: /비주얼 전략/ }).check()
  await page.getByRole('button', { name: '광고 생성하기' }).click()

  await expect(page.getByRole('heading', { name: '광고를 만들고 있습니다' })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: '광고 생성 진행률' })).toBeVisible()
  await expect(page.getByRole('status', { name: '업로드 상태' })).toHaveText('시안 4개와 참고 순위가 준비됐습니다.', { timeout: 200_000 })

  const region = page.getByRole('region', { name: '전략별 디자인 4종' })
  await expect(region.getByText('선택 전략: 비주얼')).toBeVisible({ timeout: 30_000 })
  await expect(region.getByText(/시안 상태: completed · revision 1/)).toBeVisible({ timeout: 30_000 })
  await expect(region.getByRole('article')).toHaveCount(4)
  if (process.env.PLAYWRIGHT_REQUIRE_RANKING_MODEL === '1') await expect(region.getByText(/선호 모델\(bt-logistic-v1\)/)).toBeVisible({ timeout: 60_000 })
  else await expect(region.getByText('시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다.')).toBeVisible()
  expect(paid).toBe(0)
})
