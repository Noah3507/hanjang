import { ApiError, type Draft, type UploadHandle } from './uploads'
import type { CopyState } from './copy'
import type { Facts } from './uploads'
export interface RenderCandidate {
  candidate_id: string; strategy: 'emotional' | 'price' | 'visual' | 'brand'; revision: number
  copy?: { headline: string; body: string; cta: string }; facts?: Facts
  png: { asset_id: string; url: string; width: 1080; height: 1350; revision: number }
}
export interface RenderState {
  operation: 'rendering'; status: 'pending' | 'processing' | 'completed' | 'failed'; is_current: boolean
  source_asset_id: string; copy_key: string | null; mock_copy: boolean; revision: number
  candidates: RenderCandidate[]; error: { code: string; message: string } | null; warnings: string[]
}
const base = () => (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
export async function rendering(handle: UploadHandle, start?: { asset: string; draft: Draft; copy: CopyState }): Promise<RenderState> {
  const response = await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/rendering`, {
    method: start ? 'POST' : 'GET', headers: { 'X-Hanjang-Session': handle.token, ...(start ? { 'Content-Type': 'application/json' } : {}) },
    ...(start ? { body: JSON.stringify({ expected_asset_id: start.asset, expected_copy_key: start.copy.copy_key,
      expected_input: { facts: start.draft.facts, mood: start.draft.mood, product_features: start.draft.product_features ?? null, use_address_for_copy: start.draft.use_address_for_copy ?? false } }) } : {}),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(body?.error?.message || '광고 렌더링 요청에 실패했습니다.')
  if (!body || body.operation !== 'rendering' || !['pending', 'processing', 'completed', 'failed'].includes(body.status)
    || typeof body.is_current !== 'boolean' || typeof body.mock_copy !== 'boolean' || !Array.isArray(body.candidates)
    || (body.status === 'completed' && (body.candidates.length !== 4 || new Set(body.candidates.map((c: RenderCandidate) => c.strategy)).size !== 4
      || new Set(body.candidates.map((c: RenderCandidate) => c.candidate_id)).size !== 4
      || body.candidates.some((c: RenderCandidate) => !['emotional', 'price', 'visual', 'brand'].includes(c.strategy)
        || !c.candidate_id || c.revision !== body.revision || !c.png || !/^[a-f0-9]{32}$/.test(c.png.asset_id) || c.png.width !== 1080 || c.png.height !== 1350 || c.png.revision !== body.revision)))) throw new Error('광고 응답 형식이 올바르지 않습니다.')
  return body
}
export async function preview(handle: UploadHandle, asset: string) {
  const response = await fetch(`${base()}/assets/${encodeURIComponent(asset)}`, { headers: { 'X-Hanjang-Session': handle.token } })
  if (!response.ok || !response.headers.get('Content-Type')?.startsWith('image/png')) throw new Error('광고 이미지에 접근할 수 없습니다. 만료 여부를 확인해 주세요.')
  return response.blob()
}
