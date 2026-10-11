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
    expect(screen.getByRole('heading', { name: 'Hanjang' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결 확인 중')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결됨'))
    expect(screen.getByText(/아직 구현되지 않았습니다/)).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('shows failure and recovers on retry', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ok', api_version: 'v1-draft' }) }))
    render(<App />)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결 불가'))
    fireEvent.click(screen.getByRole('button', { name: '연결 다시 확인' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('백엔드 연결됨'))
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
