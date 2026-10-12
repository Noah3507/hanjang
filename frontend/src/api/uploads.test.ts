import { afterEach, expect, it, vi } from 'vitest'
import { getInput, saveInput, uploadPhoto } from './uploads'

afterEach(() => vi.unstubAllGlobals())
it('sends multipart original and auth header, without logging or putting tokens in the URL', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ session_token: 'test-only-token' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ job_id: 'job', asset_id: 'asset' }) })
  vi.stubGlobal('fetch', fetchMock)
  const file = new File(['bytes'], 'image.png', { type: 'image/png' })
  await uploadPhoto(file)
  const [url, options] = fetchMock.mock.calls[1]
  expect(url).toBe('/api/v1/uploads')
  expect(options.headers).toEqual({ 'X-Hanjang-Session': 'test-only-token' })
  expect(options.body.get('photo')).toBe(file)
})
it('uses the approved PUT/GET draft routes with facts unchanged', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
  vi.stubGlobal('fetch', fetchMock)
  const handle = { token: 'test-only-token', upload: { job_id: 'job' } } as Parameters<typeof saveInput>[0]
  const facts = { store_name: ' 가게 ', product_name: '메뉴', price_text: '10,500 원', address: null, instagram_handle: null }
  await saveInput(handle, facts, 'warm')
  await getInput(handle)
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/jobs/job/input')
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ facts, mood: 'warm' })
  expect(fetchMock.mock.calls[0][1].method).toBe('PUT')
  expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/jobs/job/input')
})
