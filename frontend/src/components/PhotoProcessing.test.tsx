import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import PhotoProcessing from './PhotoProcessing'
import { choosePhoto, photoBlob, photoState, type PhotoState } from '../api/photos'

vi.mock('../api/photos', () => ({ choosePhoto: vi.fn(), photoBlob: vi.fn(), photoState: vi.fn() }))
const handle = { token: 'fixture', upload: { job_id: 'job', asset_id: 'original', width: 300, height: 300,
  mime_type: 'image/png' as const, sha256: 'a'.repeat(64), created_at: '', expires_at: '' } }
const initial: PhotoState = { job_id: 'job', operation: 'photo_processing', status: 'pending',
  original: handle.upload, processed: null, photo_source: 'original', warnings: [], expires_at: '' }
beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:fixture')
  URL.revokeObjectURL = vi.fn()
  vi.mocked(photoBlob).mockResolvedValue(new Blob(['fixture']))
  vi.mocked(photoState).mockResolvedValue(initial)
})
it('shows missing-model failure and keeps original selectable', async () => {
  render(<PhotoProcessing handle={handle} />)
  await waitFor(() => expect(screen.getByText('사진 처리 상태: pending · 광고 생성은 시작하지 않습니다.')).toBeInTheDocument())
  vi.mocked(photoState).mockResolvedValue({ ...initial, status: 'failed', warnings: ['PHOTO_MODEL_UNAVAILABLE'] })
  fireEvent.click(screen.getByRole('button', { name: '배경 제거 시작' }))
  await waitFor(() => expect(screen.getByText(/자동 다운로드 없이 원본/)).toBeInTheDocument())
  expect(screen.getByRole('button', { name: '처리본 사용' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '원본 사용' })).toHaveAttribute('aria-pressed', 'true')
})
it('compares a warning result and persists explicit selection via API', async () => {
  const completed: PhotoState = { ...initial, status: 'completed', processed: { ...initial.original, asset_id: 'processed' }, warnings: ['PHOTO_MASK_REVIEW_REQUIRED'] }
  vi.mocked(photoState).mockResolvedValue(completed)
  vi.mocked(choosePhoto).mockResolvedValue({ ...completed, photo_source: 'processed' })
  render(<PhotoProcessing handle={handle} />)
  await waitFor(() => expect(screen.getByAltText('배경 제거 처리본 사진')).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: '처리본 사용' }))
  await waitFor(() => expect(choosePhoto).toHaveBeenCalledWith(handle, 'processed'))
  await waitFor(() => expect(screen.getByRole('button', { name: '처리본 사용' })).toHaveAttribute('aria-pressed', 'true'))
})
it('reports server errors without showing successful processing', async () => {
  vi.mocked(photoState).mockRejectedValue(new Error('테스트용 서버 오류'))
  render(<PhotoProcessing handle={handle} />)
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('테스트용 서버 오류'))
  expect(screen.queryByAltText('배경 제거 처리본 사진')).not.toBeInTheDocument()
})
