import { test, expect } from './fixtures'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.env.PLAYWRIGHT_PYTHON || (process.platform === 'win32' ? `${root}/.venv/Scripts/python.exe` : 'python')
async function saved(page: import('@playwright/test').Page) {
  await page.goto('/')
  const sample = process.env.PLAYWRIGHT_ANALYSIS_SAMPLE
  if (sample) await page.getByLabel('상품 사진').setInputFiles(sample)
  else {
    const buffer = execFileSync(python, ['-c', "from PIL import Image;import io,sys;i=Image.new('RGB',(400,300),(150,60,30));b=io.BytesIO();i.save(b,'PNG');sys.stdout.buffer.write(b.getvalue())"])
    await page.getByLabel('상품 사진').setInputFiles({ name: 'synthetic.png', mimeType: 'image/png', buffer })
  }
  await page.getByLabel('가게명', { exact: true }).fill('  테스트 가게  ')
  await page.getByLabel('상품명', { exact: true }).fill('사용자 입력 상품')
  await page.getByLabel('가격', { exact: true }).fill(' 10,500 원 ')
  await page.getByLabel('광고 분위기').selectOption('warm')
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('button', { name: '선택 사진 분석' })).toBeEnabled()
}

test('real API: selected photo analysis, palette, offline CLIP or real model, dedup', async ({ page }, info) => {
  test.setTimeout(160_000)
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', e => { if (e.type() === 'error') errors.push(e.text()) })
  await saved(page)
  await page.getByRole('button', { name: '선택 사진 분석' }).click()
  const panel = page.getByRole('region', { name: '상품 사진 분석' })
  await expect(panel.getByText('분석 상태: completed')).toBeVisible({ timeout: 130_000 })
  await expect(panel.getByText(/#[0-9A-F]{6}/).first()).toBeVisible()
  if (process.env.PLAYWRIGHT_REQUIRE_ANALYSIS_MODEL === '1') {
    await expect(panel.getByText('CLIP: 실제 모델 시각 단서')).toBeVisible()
    await expect(panel.getByText(/cosine similarity/)).toHaveCount(12)
  } else {
    await expect(panel.getByText(/CLIP: (실제 모델 시각 단서|사용 불가)/)).toBeVisible()
  }
  await page.getByRole('button', { name: '선택 사진 분석' }).click()
  await expect(panel.getByText('분석 상태: completed')).toBeVisible()
  await expect(page.getByLabel('상품명', { exact: true })).toHaveValue('사용자 입력 상품')
  await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
  await page.screenshot({ path: info.outputPath('analysis.png'), fullPage: true })
  expect(errors).toEqual([])
})

test('simulated source conflict preserves input; simulated CLIP unavailable keeps palette', async ({ page }) => {
  await saved(page)
  await page.route('**/photo-analysis', async route => {
    if (route.request().method() === 'POST') return route.fulfill({ status: 409, json: { error: { message: '선택된 사진이 변경됐습니다.' } } })
    return route.continue()
  })
  await page.getByRole('button', { name: '선택 사진 분석' }).click()
  await expect(page.getByRole('alert')).toContainText('변경됐습니다')
  await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
  await page.unroute('**/photo-analysis')
  await page.route('**/photo-analysis', async route => {
    const response = await route.fetch()
    const body = await response.json()
    await route.fulfill({ response, json: { ...body, status: 'completed', clip: { ...body.clip, status: 'unavailable', cues: [] },
      palette: { status: 'available', colors: [{ hex: '#FF0000', rgb: [255, 0, 0], proportion: 1 }] }, warnings: ['ANALYSIS_MODEL_UNAVAILABLE'] } })
  })
  await page.getByRole('button', { name: '분석 상태 다시 조회' }).click()
  await expect(page.getByText('CLIP: 사용 불가 · 추정 단서 없음')).toBeVisible()
  await expect(page.getByText(/#FF0000/)).toBeVisible()
})

test('mobile analysis panel fits viewport', async ({ page }, info) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await saved(page)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('analysis-mobile.png'), fullPage: true })
})
