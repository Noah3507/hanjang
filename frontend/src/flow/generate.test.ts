import { beforeEach, describe, expect, it, vi } from 'vitest'
import { generateAds, GenerationCancelled, type StepId, type StepState } from './generate'
import { photoState } from '../api/photos'
import { copyState } from '../api/copy'
import { rendering } from '../api/rendering'
import { createDesigns, getDesigns, rankDesigns } from '../api/designs'

vi.mock('../api/photos', () => ({ photoState: vi.fn() }))
vi.mock('../api/copy', () => ({ copyState: vi.fn() }))
vi.mock('../api/rendering', () => ({ rendering: vi.fn() }))
vi.mock('../api/designs', () => ({ createDesigns: vi.fn(), getDesigns: vi.fn(), rankDesigns: vi.fn() }))

const handle = { token: 'test-only-token', upload: { job_id: 'job', asset_id: 'orig' } } as never
const draft = { facts: {}, mood: 'warm' } as never
const photo = (status: string, source = 'processed') => ({ status, photo_source: source, original: { asset_id: 'orig' }, processed: status === 'completed' ? { asset_id: 'cut' } : null, warnings: [] }) as never
const copy = (status: string, extra = {}) => ({ status, provider: 'mock', is_current: true, source_asset_id: 'cut', copy_key: 'k1', error: null, ...extra }) as never
const render = (status: string, extra = {}) => ({ status, is_current: true, source_asset_id: 'cut', copy_key: 'k1', revision: 3, error: null, ...extra }) as never
const designs = (status: string, extra = {}) => ({ status, is_current: true, source_revision: 3, source_asset_id: 'cut', copy_key: 'k1', ranking: null, ranking_error: null, error: null, ...extra }) as never
const ranking = { source: 'model', model_version: 'bt-logistic-v1', items: [] }

function options(approve = true) {
  const steps: [StepId, StepState][] = []
  return { steps, approvePaidCopy: vi.fn(async () => approve), onStep: (id: StepId, state: StepState) => { steps.push([id, state]) }, wait: async () => {} }
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(photoState).mockResolvedValueOnce(photo('pending')).mockResolvedValueOnce(photo('processing')).mockResolvedValue(photo('completed'))
  vi.mocked(copyState).mockResolvedValueOnce(copy('pending')).mockResolvedValueOnce(copy('processing')).mockResolvedValue(copy('completed'))
  vi.mocked(rendering).mockResolvedValueOnce(render('pending')).mockResolvedValueOnce(render('processing')).mockResolvedValue(render('completed'))
  vi.mocked(getDesigns).mockResolvedValueOnce(designs('pending')).mockResolvedValue(designs('completed'))
  vi.mocked(createDesigns).mockResolvedValue(designs('processing'))
  vi.mocked(rankDesigns).mockResolvedValue(designs('completed', { ranking }))
})

describe('one-click generation', () => {
  it('runs every step in order with the processed photo and the chosen strategy', async () => {
    const o = options()
    const result = await generateAds(handle, draft, 'visual', o)
    expect(o.steps).toEqual([['photo', 'running'], ['photo', 'done'], ['copy', 'running'], ['copy', 'done'], ['designs', 'running'], ['designs', 'done'], ['ranking', 'running'], ['ranking', 'done']])
    expect(photoState).toHaveBeenNthCalledWith(2, handle, true)
    expect(copyState).toHaveBeenNthCalledWith(2, handle, { asset: 'cut', draft })
    expect(rendering).toHaveBeenNthCalledWith(2, handle, expect.objectContaining({ asset: 'cut' }))
    expect(createDesigns).toHaveBeenCalledWith(handle, 'visual', expect.objectContaining({ revision: 3 }))
    expect(rankDesigns).toHaveBeenCalledWith(handle, 'visual', expect.anything())
    expect(o.approvePaidCopy).not.toHaveBeenCalled()
    expect(result.designs.ranking).toEqual(ranking)
    expect(result.rankingError).toBeNull()
  })
  it('reuses finished current results instead of starting them again', async () => {
    vi.mocked(photoState).mockReset().mockResolvedValue(photo('completed'))
    vi.mocked(copyState).mockReset().mockResolvedValue(copy('completed', { provider: 'openai' }))
    vi.mocked(rendering).mockReset().mockResolvedValue(render('completed'))
    vi.mocked(getDesigns).mockReset().mockResolvedValue(designs('completed', { ranking }))
    const o = options()
    await generateAds(handle, draft, 'price', o)
    expect(photoState).toHaveBeenCalledTimes(1)
    expect(copyState).toHaveBeenCalledTimes(1)
    expect(rendering).toHaveBeenCalledTimes(1)
    expect(createDesigns).not.toHaveBeenCalled()
    expect(rankDesigns).not.toHaveBeenCalled()
    expect(o.approvePaidCopy).not.toHaveBeenCalled()
  })
  it('keeps the original photo when the server did not select the processed one', async () => {
    vi.mocked(photoState).mockReset().mockResolvedValue(photo('completed', 'original'))
    vi.mocked(copyState).mockReset().mockResolvedValueOnce(copy('pending')).mockResolvedValue(copy('completed', { source_asset_id: 'orig' }))
    vi.mocked(rendering).mockReset().mockResolvedValueOnce(render('pending')).mockResolvedValue(render('completed', { source_asset_id: 'orig' }))
    vi.mocked(getDesigns).mockReset().mockResolvedValue(designs('completed', { source_asset_id: 'orig', ranking }))
    await generateAds(handle, draft, 'price', options())
    expect(copyState).toHaveBeenNthCalledWith(2, handle, { asset: 'orig', draft })
  })
  it('never starts a paid copy call without approval', async () => {
    vi.mocked(copyState).mockReset().mockResolvedValue(copy('pending', { provider: 'openai' }))
    const o = options(false)
    await expect(generateAds(handle, draft, 'price', o)).rejects.toBeInstanceOf(GenerationCancelled)
    expect(o.approvePaidCopy).toHaveBeenCalledTimes(1)
    expect(copyState).toHaveBeenCalledTimes(1)
    expect(rendering).not.toHaveBeenCalled()
    expect(o.steps.at(-1)).toEqual(['copy', 'failed'])
  })
  it('starts the paid copy call once after approval', async () => {
    vi.mocked(copyState).mockReset().mockResolvedValueOnce(copy('pending', { provider: 'openai' })).mockResolvedValue(copy('completed', { provider: 'openai' }))
    const o = options(true)
    await generateAds(handle, draft, 'price', o)
    expect(vi.mocked(copyState).mock.calls.filter((call) => call[1]).length).toBe(1)
  })
  it('stops with the server message when a step fails', async () => {
    vi.mocked(copyState).mockReset().mockResolvedValueOnce(copy('pending')).mockResolvedValue(copy('failed', { error: { code: 'X', message: '문구 실패' } }))
    const o = options()
    await expect(generateAds(handle, draft, 'price', o)).rejects.toThrow('문구 실패')
    expect(rendering).not.toHaveBeenCalled()
  })
  it('returns the designs without a rank when ranking fails', async () => {
    vi.mocked(rankDesigns).mockReset().mockResolvedValue(designs('completed', { ranking_error: { code: 'RANKING', message: '모델을 사용할 수 없습니다.' } }))
    const o = options()
    const result = await generateAds(handle, draft, 'price', o)
    expect(result.designs.ranking).toBeNull()
    expect(result.rankingError).toBe('모델을 사용할 수 없습니다.')
    expect(o.steps.at(-1)).toEqual(['ranking', 'failed'])
  })
  it('stops between steps once cancelled', async () => {
    let cancelled = false
    const o = { ...options(), cancelled: () => cancelled }
    o.onStep = (id, state) => { if (id === 'photo' && state === 'done') cancelled = true }
    await expect(generateAds(handle, draft, 'price', o)).rejects.toBeInstanceOf(GenerationCancelled)
    expect(copyState).not.toHaveBeenCalled()
  })
})
