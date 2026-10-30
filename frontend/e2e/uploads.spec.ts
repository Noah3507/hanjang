import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { test, expect } from './fixtures'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.env.PLAYWRIGHT_PYTHON || (process.platform === 'win32' ? `${root}/.venv/Scripts/python.exe` : 'python')
function png(side = 300, fmt = 'PNG') {
  return execFileSync(python, ['-c', `import io,sys; from PIL import Image; b=io.BytesIO(); Image.new('RGB',(${side},${side}),'#a87840').save(b,format='${fmt}'); sys.stdout.buffer.write(b.getvalue())`], { cwd: root })
}
async function fill(page: import('@playwright/test').Page) {
  await page.getByLabel('가게명', { exact: true }).fill('  테스트 가게  ')
  await page.getByLabel('상품명', { exact: true }).fill('한글 메뉴 🍜')
  await page.getByLabel('가격', { exact: true }).fill(' 10,500 원 ')
  await page.getByLabel('광고 분위기').selectOption('warm')
}
test.beforeEach(async ({ page }) => { await page.goto('/') })

for (const [fmt, mime] of [['PNG', 'image/png'], ['JPEG', 'image/jpeg']]) {
  test(`${fmt}: input, real upload, save, original bytes and reload`, async ({ page, request }, info) => {
    const original = png(300, fmt)
    await page.getByLabel('상품 사진').setInputFiles({ name: `fixture.${fmt === 'JPEG' ? 'jpg' : 'png'}`, mimeType: mime, buffer: original })
    await expect(page.getByAltText('원본 상품 사진 미리보기')).toBeVisible()
    await fill(page)
    const uploadEvent = page.waitForResponse((r) => r.url().endsWith('/api/v1/uploads') && r.request().method() === 'POST')
    const sessionEvent = page.waitForResponse((r) => r.url().endsWith('/api/v1/sessions'))
    await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
    const metadata = await (await uploadEvent).json()
    const session = await (await sessionEvent).json()
    await expect(page.getByRole('region', { name: '저장된 상품 정보' })).toBeVisible()
    expect(metadata.sha256).toBe(createHash('sha256').update(original).digest('hex'))
    const response = await request.get(`/api/v1/assets/${metadata.asset_id}`, { headers: { 'X-Hanjang-Session': session.session_token } })
    expect(response.status()).toBe(200)
    expect(await response.body()).toEqual(original)
    await page.getByLabel('상품명', { exact: true }).fill('로컬 임시 수정')
    await page.getByRole('button', { name: '저장 정보 다시 조회' }).click()
    await expect(page.getByLabel('상품명', { exact: true })).toHaveValue('한글 메뉴 🍜')
    await expect(page.getByLabel('가게명', { exact: true })).toHaveValue('  테스트 가게  ')
    await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
    await page.reload()
    await page.getByRole('button', { name: '저장 정보 다시 조회' }).click()
    await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
    await expect(page.getByText(/작업 상태: pending/)).toBeVisible()
    await page.screenshot({ path: info.outputPath('upload-saved.png'), fullPage: true })
    await expect(page.getByText(/실제 ML 순위·문구 편집·다운로드는 아직 구현되지/)).toBeVisible()
  })
}

test('required fields and unsupported files block submission', async ({ page }) => {
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('alert')).toContainText('입력 항목')
  await page.getByLabel('상품 사진').setInputFiles({ name: 'fixture.svg', mimeType: 'image/svg+xml', buffer: Buffer.from('<svg/>') })
  await expect(page.getByText('10 MiB 이하의 JPG/PNG 사진을 선택해 주세요.')).toBeVisible()
})

test('actual backend rejects a small image and preserves input', async ({ page }) => {
  await fill(page)
  await page.getByLabel('상품 사진').setInputFiles({ name: 'small.png', mimeType: 'image/png', buffer: png(100) })
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('alert')).toContainText('256px')
  await expect(page.getByLabel('가격', { exact: true })).toHaveValue(' 10,500 원 ')
  await expect(page.getByRole('region', { name: '저장된 상품 정보' })).toHaveCount(0)
})

test('simulated draft failure is visible and retry saves through real API', async ({ page }) => {
  await fill(page)
  await page.getByLabel('상품 사진').setInputFiles({ name: 'fixture.png', mimeType: 'image/png', buffer: png() })
  await page.route('**/jobs/*/input', (route) => route.request().method() === 'PUT'
    ? route.fulfill({ status: 503, json: { error: { message: '테스트용 저장 오류', field_errors: [] } } }) : route.continue())
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('alert')).toContainText('테스트용 저장 오류')
  await page.unroute('**/jobs/*/input')
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('region', { name: '저장된 상품 정보' })).toBeVisible()
})

test('mobile upload form has no horizontal overflow', async ({ page }, info) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await fill(page)
  await page.getByLabel('상품 사진').setInputFiles({ name: 'fixture.png', mimeType: 'image/png', buffer: png() })
  await page.getByRole('button', { name: '상품 정보와 사진 저장' }).click()
  await expect(page.getByRole('region', { name: '저장된 상품 정보' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: info.outputPath('upload-mobile.png'), fullPage: true })
})
