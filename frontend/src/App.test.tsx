import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

describe('backend connection status', () => {
  it('shows checking then verified connection without implying ad features exist', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ status: 'ok', api_version: 'v1-draft' }),
    }))
    render(<App />)
    expect(screen.getByRole('heading', { name: '한장' })).toBeInTheDocument()
    expect(screen.queryByText(/SERVICE FOUNDATION|FastAPI/)).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결 확인 중')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결됨'))
    expect(screen.getByText(/추천 순위와 가독성 진단은 따로 계산한/)).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('shows failure and recovers on retry', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ok', api_version: 'v1-draft' }) }))
    render(<App />)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결 불가'))
    expect(screen.getByRole('heading', { name: '서버 연결 상태' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '연결 다시 확인' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결됨'))
    expect(screen.queryByRole('heading', { name: '서버 연결 상태' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '연결 다시 확인' })).toBeEnabled()
  })

  it.each([
    { ok: false, json: async () => ({}) },
    { ok: true, json: async () => ({ status: 'ok', api_version: 'other' }) },
  ])('does not report an invalid backend response as connected', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
    render(<App />)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결 불가'))
  })
})
