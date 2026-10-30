import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import RankingResults from './RankingResults'
import { rankingState, type RankingState } from '../api/ranking'
import type { RenderState } from '../api/rendering'
import type { UploadHandle } from '../api/uploads'
vi.mock('../api/ranking', () => ({ rankingState: vi.fn() }))
const handle = { token: 'fake', upload: { job_id: 'job' } } as UploadHandle
const current = { status: 'completed', is_current: true, revision: 1, source_asset_id: 'source', copy_key: 'copy',
  candidates: ['emotional','price','visual','brand'].map(strategy => ({ candidate_id: strategy, strategy, revision: 1, png: { asset_id: strategy } })) } as RenderState
const pending = { operation: 'ranking', job_id: 'job', status: 'pending', is_current: false, revision: 1, ranking: null, warnings: [], error: null } as RankingState
const complete = { ...pending, status: 'completed', is_current: true, ranking: {
  source: 'mock', model_version: 'mock-v1', feature_version: null, revision: 1, pairwise: null,
  items: ['visual','emotional','price','brand'].map((candidate_id,i) => ({ candidate_id, score: .8-i*.2, rank: i+1 })),
} } as RankingState
beforeEach(() => { vi.resetAllMocks(); vi.mocked(rankingState).mockResolvedValue(pending) })
test('shows unranked state, then demonstration ranks without scores or probabilities', async () => {
  render(<RankingResults handle={handle} render={current} disabled={false} />)
  expect(await screen.findByText('아직 생성된 순위가 없습니다.')).toBeInTheDocument()
  vi.mocked(rankingState).mockResolvedValue(complete)
  fireEvent.click(screen.getByRole('button', { name: '임시 순위 확인' }))
  expect(await screen.findAllByRole('listitem')).toHaveLength(4)
  expect(screen.getByText('1위 · 비주얼 · visual')).toBeInTheDocument()
  expect(screen.getByText('시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다')).toBeInTheDocument()
  expect(screen.queryByText(/0\.8/)).not.toBeInTheDocument()
  expect(rankingState).toHaveBeenLastCalledWith(handle, current)
})
test('stale response and disabled inputs never display previous ranks', async () => {
  vi.mocked(rankingState).mockResolvedValue({ ...complete, is_current: false })
  const { rerender } = render(<RankingResults handle={handle} render={current} disabled={false} />)
  expect(await screen.findByText(/현재 광고와 일치하는 순위가 아닙니다/)).toBeInTheDocument()
  expect(screen.queryByRole('list')).not.toBeInTheDocument()
  rerender(<RankingResults handle={handle} render={current} disabled />)
  expect(screen.getByRole('button', { name: '임시 순위 확인' })).toBeDisabled()
})
test('old delayed response cannot attach to a newer revision', async () => {
  let release!: (value: RankingState) => void
  vi.mocked(rankingState).mockImplementationOnce(() => new Promise(resolve => { release=resolve }))
  const { rerender } = render(<RankingResults handle={handle} render={current} disabled={false} />)
  await waitFor(() => expect(rankingState).toHaveBeenCalledTimes(1))
  rerender(<RankingResults handle={handle} render={{ ...current, revision: 2 }} disabled={false} />)
  await act(async () => release(complete))
  expect(screen.queryByRole('list')).not.toBeInTheDocument()
})
test('unknown ID, network failure and retry are visible without losing advertisements', async () => {
  vi.mocked(rankingState).mockRejectedValueOnce(new Error('네트워크 오류'))
  render(<RankingResults handle={handle} render={current} disabled={false} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('네트워크 오류')
  vi.mocked(rankingState).mockResolvedValue({ ...complete, ranking: { ...complete.ranking!, items: complete.ranking!.items.map((i,n) => n ? i : { ...i, candidate_id: 'unknown' }) } })
  fireEvent.click(screen.getByRole('button', { name: '임시 순위 확인' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('일치하지 않습니다'))
  vi.mocked(rankingState).mockResolvedValue(complete)
  fireEvent.click(screen.getByRole('button', { name: '임시 순위 확인' }))
  expect(await screen.findAllByRole('listitem')).toHaveLength(4)
})
