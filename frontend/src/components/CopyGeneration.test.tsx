import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import CopyGeneration from './CopyGeneration'
import type { Draft, UploadHandle } from '../api/uploads'
const handle = { token: 'test-session', upload: { job_id: 'job' } } as UploadHandle
const draft: Draft = { job_id: 'job', status: 'pending', facts: { store_name: '가게', product_name: '상품', price_text: ' 10,500 원 ', address: null, instagram_handle: null }, mood: 'warm', expires_at: '', product_features: '바삭한 식감', use_address_for_copy: false }
const pending = { operation: 'copy_generation', status: 'pending', provider: 'mock', model: 'mock-copy-v1', is_current: true, source_asset_id: 'asset', variants: [], warnings: [], attempts: [], error: null }
const variants = ['emotional', 'price', 'visual', 'brand'].map(strategy => ({ strategy, copy: { headline: strategy+' 예시', body: '', cta: '' } }))
afterEach(() => vi.unstubAllGlobals())

it('explicitly shows Mock and submits the exact saved extended snapshot', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json(pending)).mockResolvedValueOnce(Response.json({ ...pending, ...draft, status: 'completed', variants }))
  vi.stubGlobal('fetch', fetch)
  render(<CopyGeneration handle={handle} draft={draft} asset="asset" disabled={false} />)
  await waitFor(() => expect(screen.getByRole('button', { name: '4전략 카피 생성' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '4전략 카피 생성' }))
  expect(await screen.findByRole('article', { name: '감성 전략 카피' })).toBeInTheDocument()
  expect(screen.getAllByRole('article')).toHaveLength(4)
  const body = JSON.parse(fetch.mock.calls[1][1].body)
  expect(body.expected_input).toEqual({ facts: draft.facts, mood: draft.mood, product_features: draft.product_features, use_address_for_copy: false })
  expect(screen.getByText(/고정 예시이며 실제 LLM/)).toBeInTheDocument()
})
it('displays stale results and exact saved facts', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...pending, ...draft, status: 'completed', variants, is_current: false })))
  render(<CopyGeneration handle={handle} draft={draft} asset="new-asset" disabled={false} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('이전 입력 또는 사진')
  expect(screen.getByText(/원문 사실:/)).toHaveTextContent('10,500 원')
})
it('handles conflict without showing fake success', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(Response.json(pending)).mockResolvedValueOnce(Response.json({ error: { message: '입력 변경' } }, { status: 409 })))
  render(<CopyGeneration handle={handle} draft={draft} asset="asset" disabled={false} />)
  await waitFor(() => expect(screen.getByRole('button', { name: '4전략 카피 생성' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: '4전략 카피 생성' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('입력 변경')
  expect(screen.queryByRole('article')).not.toBeInTheDocument()
})
it('rejects a duplicate strategy response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ ...pending, status: 'completed', variants: variants.map(v => ({ ...v, strategy: 'price' })) })))
  render(<CopyGeneration handle={handle} draft={draft} asset="asset" disabled={false} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('응답 형식')
})
