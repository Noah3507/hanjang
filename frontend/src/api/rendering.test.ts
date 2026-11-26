import { afterEach, expect, test, vi } from 'vitest'
import { rendering, preview } from './rendering'
import type { Draft, UploadHandle } from './uploads'
import type { CopyState } from './copy'
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
const facts = { store_name: '가게', product_name: '상품', price_text: '10,000원', address: null, instagram_handle: null }
const pending = { operation: 'rendering', status: 'processing', is_current: true, mock_copy: true, candidates: [] }
// The server compares expected_input with the whole saved input; a missing goal or photo mode reads as the default and fails with 409.
test('render request carries the saved ad goal and photo mode', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(pending))
  vi.stubGlobal('fetch', fetch)
  const draft = { job_id: 'job', status: 'pending', facts, mood: 'warm', expires_at: '', product_features: null, use_address_for_copy: false, ad_goal: 'order', photo_mode: 'original' } as Draft
  await rendering(handle, { asset: 'asset', draft, copy: { copy_key: 'key' } as CopyState })
  expect(JSON.parse(fetch.mock.calls[0][1].body).expected_input).toEqual({ facts, mood: 'warm', product_features: null, use_address_for_copy: false, ad_goal: 'order', photo_mode: 'original' })
})
test('older saved input without the new fields sends the server defaults', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json(pending))
  vi.stubGlobal('fetch', fetch)
  const draft = { job_id: 'job', status: 'pending', facts, mood: 'warm', expires_at: '' } as Draft
  await rendering(handle, { asset: 'asset', draft, copy: { copy_key: 'key' } as CopyState })
  expect(JSON.parse(fetch.mock.calls[0][1].body).expected_input).toMatchObject({ product_features: null, use_address_for_copy: false, ad_goal: 'menu_promotion', photo_mode: 'cutout' })
})
