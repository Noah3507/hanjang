import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import AdResults from './AdResults'
import { preview, type RenderCandidate } from '../api/rendering'
import type { UploadHandle } from '../api/uploads'
vi.mock('../api/rendering', () => ({ preview: vi.fn() }))
const handle = { token: 'fake', upload: { job_id: 'job' } } as UploadHandle
const candidates = [{ candidate_id: 'c', strategy: 'visual', revision: 1, png: { asset_id: 'asset' } }] as RenderCandidate[]
beforeEach(() => { vi.resetAllMocks(); URL.createObjectURL=vi.fn(() => 'blob:protected'); URL.revokeObjectURL=vi.fn() })
test('failed protected image can be retried; refresh cleans blob URL', async () => {
  vi.mocked(preview).mockRejectedValueOnce(new Error('401')).mockResolvedValue(new Blob(['png']))
  const { unmount } = render(<AdResults handle={handle} candidates={candidates} snapshot="1" />)
  expect(await screen.findByRole('alert')).toHaveTextContent('접근하지 못했습니다')
  fireEvent.click(screen.getByRole('button', { name: '이미지 다시 조회 · 비주얼' }))
  expect(await screen.findByRole('button', { name: '비주얼 광고 확대 보기' })).toBeInTheDocument()
  expect(preview).toHaveBeenCalledTimes(2)
  expect(preview).toHaveBeenLastCalledWith(handle, 'asset')
  unmount(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:protected')
})
