import { test, expect } from './fixtures'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.env.PLAYWRIGHT_PYTHON || (process.platform === 'win32' ? `${root}/.venv/Scripts/python.exe` : 'python')
function fixture() {
  return execFileSync(python, ['-c', "from PIL import Image,ImageDraw;import io,sys;i=Image.new('RGB',(640,480),'#466b8a');d=ImageDraw.Draw(i);d.ellipse((105,55,535,425),fill='#eeeeee');d.ellipse((145,95,495,385),fill='#e87720');b=io.BytesIO();i.save(b,'PNG');sys.stdout.buffer.write(b.getvalue())"])
}
async function saved(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByLabel('상품 사진').setInputFiles({ name: 'synthetic.png', mimeType: 'image/png', buffer: fixture() })
  await page.getByLabel('가게명', { exact: true }).fill('  테스트 가게  ')
  await page.getByLabel('상품명', { exact: true }).fill('합성 테스트 상품')
  await page.getByLabel('가격', { exact: true }).fill(' 10,500 원 ')
  await page.getByLabel('광고 분위기').selectOption('warm')
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('button', { name: '배경 제거 시작' })).toBeEnabled()
}
test('real API: process or offline fallback, compare and preserve facts', async ({ page }, info) => {
  test.setTimeout(150_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  await saved(page)
  await page.getByRole('button', { name: '배경 제거 시작' }).click()
  const panel = page.getByRole('region', { name: '사진 전처리' })
  await expect(panel.getByText(/사진 처리 상태: (completed|failed)/)).toBeVisible({ timeout: 125_000 })
  if (await panel.getByAltText('배경 제거 처리본 사진').count()) {
    await expect(panel.getByAltText('배경 제거 처리본 사진')).toBeVisible()
    await panel.getByRole('button', { name: '원본 사용' }).click()
    await expect(panel.getByRole('button', { name: '원본 사용' })).toHaveAttribute('aria-pressed', 'true')
    await panel.getByRole('button', { name: '처리본 사용' }).click()
    await expect(panel.getByRole('button', { name: '처리본 사용' })).toHaveAttribute('aria-pressed', 'true')
  } else {
    if (process.env.PLAYWRIGHT_REQUIRE_PHOTO_MODEL === '1') throw new Error('Real model result required for this local verification')
    await expect(panel.getByText(/배경 제거 모델이 없습니다/)).toBeVisible()
    await expect(panel.getByRole('button', { name: '처리본 사용' })).toBeDisabled()
  }
  await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
  await page.screenshot({ path: info.outputPath('photo-processing.png'), fullPage: true })
  expect(errors).toEqual([])
})

test('simulated processing failure visibly selects original', async ({ page }) => {
  await saved(page)
  await page.route('**/jobs/*/photo-processing', async route => {
    const response = await route.fetch()
    const body = await response.json()
    await route.fulfill({ status: route.request().method() === 'POST' ? 202 : 200,
      json: { ...body, status: 'failed', processed: null, photo_source: 'original', warnings: ['PHOTO_PROCESSING_TIMEOUT'] } })
  })
  await page.getByRole('button', { name: '배경 제거 시작' }).click()
  await expect(page.getByText(/제한 시간이 초과됐습니다/)).toBeVisible()
  await expect(page.getByRole('button', { name: '원본 사용' })).toHaveAttribute('aria-pressed', 'true')
})

test('mobile comparison has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await saved(page)
  await expect(page.getByAltText('서버 보존 원본 사진')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
