import { afterEach, expect, test, vi } from 'vitest'
import { rankingState } from './ranking'
import type { UploadHandle } from './uploads'
import type { RenderState } from './rendering'
const handle = { token: 'test-only', upload: { job_id: 'job' } } as UploadHandle
const result = () => ({ operation: 'ranking', job_id: 'job', status: 'completed', is_current: true, revision: 2, warnings: [], error: null,
  ranking: { source: 'mock', model_version: 'mock-v1', feature_version: null, revision: 2, pairwise: null,
    items: ['a','b','c','d'].map((candidate_id, i) => ({ candidate_id, score: .8-i*.2, rank: i+1 })) } })
afterEach(() => vi.unstubAllGlobals())
test('GET is read-only; POST sends authenticated exact candidate/revision snapshot', async () => {
  const fetch = vi.fn().mockImplementation(async () => Response.json(result())); vi.stubGlobal('fetch', fetch)
  await rankingState(handle)
  expect(fetch.mock.calls[0][1].method).toBe('GET')
  const render = { revision: 2, candidates: ['a','b','c','d'].map(candidate_id => ({ candidate_id })) } as RenderState
  await rankingState(handle, render)
  expect(fetch.mock.calls[1][1].headers['X-Hanjang-Session']).toBe('test-only')
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ expected_render_revision: 2, expected_candidate_ids: ['a','b','c','d'] })
})
test.each(['duplicate','order','probability','features','revision','wrong-job','nonfinite'])('rejects malformed response %s', async mode => {
  const body = result()
  if (mode === 'duplicate') body.ranking.items[1].candidate_id = 'a'
  if (mode === 'order') body.ranking.items.reverse()
  if (mode === 'probability') Object.assign(body.ranking, { pairwise: {} })
  if (mode === 'features') Object.assign(body.ranking, { feature_version: 'fake' })
  if (mode === 'revision') body.ranking.revision++
  if (mode === 'wrong-job') body.job_id = 'another'
  if (mode === 'nonfinite') body.ranking.items[0].score = Infinity
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(body)))
  await expect(rankingState(handle)).rejects.toThrow('응답 형식')
})
test('permission and conflict errors do not become success', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: { message: '광고가 변경됐습니다' } }, { status: 409 })))
  await expect(rankingState(handle)).rejects.toThrow('광고가 변경됐습니다')
})
