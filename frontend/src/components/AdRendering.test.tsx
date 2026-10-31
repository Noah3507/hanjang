import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, test, expect, beforeEach } from 'vitest'
import AdRendering from './AdRendering'
import { rendering, preview } from '../api/rendering'
import type { CopyState } from '../api/copy'
import type { Draft, UploadHandle } from '../api/uploads'
vi.mock('../api/rendering', () => ({ rendering: vi.fn(), preview: vi.fn() }))
vi.mock('../api/editing', () => ({ editing: vi.fn(async () => ({operation:'editing',status:'pending',is_current:false})), downloadAd: vi.fn() }))
vi.mock('../api/ranking', () => ({ rankingState: vi.fn(async () => ({ status: 'pending', ranking: null })) }))
const handle = { token: 'fake', upload: { job_id: 'job' } } as UploadHandle
const draft = { facts: {}, mood: 'warm' } as Draft
const copy = { copy_key: 'key', status: 'completed', is_current: true } as CopyState
const state = { operation: 'rendering', status: 'completed', is_current: true, source_asset_id: 'asset', copy_key: 'key', mock_copy: true, revision: 1, error: null, warnings: [],
  candidates: ['emotional', 'price', 'visual', 'brand'].map(strategy => ({ candidate_id: strategy, strategy, png: { asset_id: strategy } })) }
beforeEach(() => {
  vi.mocked(rendering).mockResolvedValue(state as never)
  vi.mocked(preview).mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  URL.createObjectURL = vi.fn(() => 'blob:fake'); URL.revokeObjectURL = vi.fn()
})
test('four protected PNG previews, Mock and exact request snapshot', async () => {
  render(<AdRendering handle={handle} draft={draft} asset="asset" copy={copy} disabled={false} />)
  expect(await screen.findAllByRole('img')).toHaveLength(4)
  expect(screen.getByText(/Mock 카피 사용/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '광고 4장 렌더링' }))
  await waitFor(() => expect(rendering).toHaveBeenCalledWith(handle, { asset: 'asset', draft, copy }))
})
test('stale result is visibly distinguished and rendering blocked without current copy', async () => {
  vi.mocked(rendering).mockResolvedValue({ ...state, is_current: false } as never)
  render(<AdRendering handle={handle} draft={draft} asset="asset" copy={{ ...copy, is_current: false }} disabled={false} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('최신 결과가 아닙니다')
  expect(screen.getByRole('button', { name: '광고 4장 렌더링' })).toBeDisabled()
})
test('render failure and manual state refresh', async () => {
  vi.mocked(rendering).mockResolvedValue({ ...state, status: 'failed', candidates: [], error: { code: 'RENDER_TIMEOUT', message: '시간 초과' } } as never)
  render(<AdRendering handle={handle} draft={draft} asset="asset" copy={copy} disabled={false} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('RENDER_TIMEOUT')
  fireEvent.click(screen.getByRole('button', { name: '광고 상태 다시 조회' }))
  await waitFor(() => expect(rendering).toHaveBeenCalledTimes(2))
})
test('image access failure is shown without pretending success', async () => {
  vi.mocked(preview).mockRejectedValue(new Error('expired'))
  render(<AdRendering handle={handle} draft={draft} asset="asset" copy={copy} disabled={false} />)
  expect(await screen.findAllByRole('alert')).toHaveLength(4)
  expect(screen.queryAllByRole('img')).toHaveLength(0)
})
test('pending loading and API failure', async () => {
  vi.mocked(rendering).mockRejectedValue(new Error('서버 오류'))
  render(<AdRendering handle={handle} draft={draft} asset="asset" copy={copy} disabled={false} />)
  expect(screen.getByRole('status')).toHaveTextContent('조회 중')
  expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류')
})
