import { afterEach, expect, test, vi } from 'vitest'
import { rendering, preview } from './rendering'
import type { UploadHandle } from './uploads'
const handle = { token: 'fake-token', upload: { job_id: 'job' } } as UploadHandle
afterEach(() => vi.unstubAllGlobals())
test('rejects incomplete completed candidate set', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ operation: 'rendering', status: 'completed', is_current: true, mock_copy: true, candidates: [] })))
  await expect(rendering(handle)).rejects.toThrow('응답 형식')
})
test('protected asset uses explicit authentication and encoded ID', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(new Blob(['png']), { headers: { 'Content-Type': 'image/png' } }))
  vi.stubGlobal('fetch', fetch)
  await preview(handle, 'abc')
  expect(fetch).toHaveBeenCalledWith('/api/v1/assets/abc', { headers: { 'X-Hanjang-Session': 'fake-token' } })
})
test('expired asset and server conflict are reported', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: { message: '사진이 변경됐습니다.' } }, { status: 409 })))
  await expect(rendering(handle)).rejects.toThrow('사진이 변경됐습니다')
  await expect(preview(handle, 'abc')).rejects.toThrow('접근할 수 없습니다')
})
