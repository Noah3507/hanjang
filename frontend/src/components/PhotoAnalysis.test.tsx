import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PhotoAnalysis from './PhotoAnalysis'
import type { UploadHandle } from '../api/uploads'

const handle = { token: 'test-only', upload: { job_id: 'job' } } as UploadHandle
const state = { job_id: 'job', operation: 'photo_analysis', status: 'pending', source_asset_id: 'asset', photo_source: 'original', is_current: true,
  analysis_version: 'v1', expires_at: '', warnings: [], error: null,
  clip: { status: 'unavailable', cues: [] }, palette: { status: 'unavailable', colors: [] } }
afterEach(() => vi.unstubAllGlobals())
describe('product photo analysis', () => {
  it('sends expected asset and displays real API-shaped cues and palette as hints', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(Response.json(state)).mockResolvedValueOnce(Response.json({ ...state, status: 'completed',
      clip: { status: 'available', cues: [{ candidate_id: 'drink', label: '음료 단서', similarity: .3 }] },
      palette: { status: 'available', colors: [{ hex: '#FF0000', rgb: [255, 0, 0], proportion: 1 }] } }))
    vi.stubGlobal('fetch', fetch)
    render(<PhotoAnalysis handle={handle} asset="asset" disabled={false} />)
    await waitFor(() => expect(screen.getByRole('button', { name: '선택 사진 분석' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '선택 사진 분석' }))
    expect(await screen.findByText(/음료 단서: 0.300/)).toBeInTheDocument()
    expect(screen.getByText(/#FF0000/)).toBeInTheDocument()
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ expected_asset_id: 'asset' })
    expect(screen.getByText(/확률·음식 사실/)).toBeInTheDocument()
  })
  it('shows stale data warning and partial unavailable state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...state, status: 'completed', is_current: false, warnings: ['ANALYSIS_MODEL_UNAVAILABLE'] })))
    render(<PhotoAnalysis handle={handle} asset="changed" disabled={false} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('이전 사진')
    expect(screen.getByText(/사용 불가 · 추정 단서 없음/)).toBeInTheDocument()
  })
  it('shows conflict error without a fake result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json(state)).mockResolvedValueOnce(Response.json({ error: { message: '선택 사진 변경' } }, { status: 409 })))
    render(<PhotoAnalysis handle={handle} asset="asset" disabled={false} />)
    await waitFor(() => expect(screen.getByRole('button', { name: '선택 사진 분석' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '선택 사진 분석' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('선택 사진 변경')
  })
  it('rejects a malformed result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...state, palette: { colors: [{ hex: 'invalid', proportion: 2 }] } })))
    render(<PhotoAnalysis handle={handle} asset="asset" disabled={false} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('응답 형식')
  })
})
