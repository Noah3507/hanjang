import { test, expect } from './fixtures'

test('desktop: actual API connection and explicit unimplemented feature notice', async ({ page, request }, testInfo) => {
  await test.step('FastAPI and Vite proxy return the health contract', async () => {
    for (const url of [`http://127.0.0.1:${process.env.PLAYWRIGHT_BACKEND_PORT || '8000'}/health`, '/api/v1/health']) {
      const response = await request.get(url)
      expect(response.ok()).toBeTruthy()
      expect(await response.json()).toEqual({ status: 'ok', api_version: 'v1-draft' })
    }
  })
  await test.step('open the React page and verify a real connected state', async () => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Hanjang', exact: true })).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('백엔드 연결됨')
    await expect(page.getByRole('button', { name: '연결 다시 확인' })).toBeEnabled()
  })
  await test.step('show implemented photo tools and distinguish unimplemented ads', async () => {
    await expect(page.getByText('상품 입력·원본 업로드·배경 제거와 사진 선택을 제공합니다. 광고 생성·선호 순위·문구 편집·다운로드는 아직 구현되지 않았습니다.')).toBeVisible()
    await expect(page.getByLabel('상품명', { exact: true })).toBeVisible()
    await expect(page.locator('input[type="file"]')).toHaveCount(1)
  })
  const path = testInfo.outputPath('desktop.png')
  await page.screenshot({ path, fullPage: true })
  await testInfo.attach('desktop', { path, contentType: 'image/png' })
})

test('checking: pending health request disables retry until verified', async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/health', async (route) => {
    await gate
    await route.fulfill({ json: { status: 'ok', api_version: 'v1-draft' } })
  })
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('백엔드 연결 확인 중')
  await expect(page.getByRole('button', { name: '연결 다시 확인' })).toBeDisabled()
  release()
  await expect(page.getByRole('status')).toHaveText('백엔드 연결됨')
})

test('failure and retry: simulated API error recovers through the real backend', async ({ page }) => {
  await test.step('simulate HTTP 503 without stopping the user server', async () => {
    await page.route('**/api/v1/health', (route) => route.fulfill({ status: 503, body: 'test-only failure' }))
    await page.goto('/')
    await expect(page.getByRole('status')).toHaveText('백엔드 연결 불가')
  })
  await test.step('remove the simulation and retry the real API', async () => {
    await page.unroute('**/api/v1/health')
    await page.getByRole('button', { name: '연결 다시 확인' }).click()
    await expect(page.getByRole('status')).toHaveText('백엔드 연결됨')
  })
})

test('invalid contract: simulated unexpected payload is not reported as connected', async ({ page }) => {
  await page.route('**/api/v1/health', (route) => route.fulfill({ json: { status: 'ok', api_version: 'unknown' } }))
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('백엔드 연결 불가')
})

test('mobile: 375px viewport keeps status and retry accessible', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('백엔드 연결됨')
  await expect(page.getByRole('button', { name: '연결 다시 확인' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  const path = testInfo.outputPath('mobile.png')
  await page.screenshot({ path, fullPage: true })
  await testInfo.attach('mobile', { path, contentType: 'image/png' })
})
