import { ApiError, type UploadHandle, type Draft, type Facts } from './uploads'
export interface CopyState {
  job_id: string; operation: 'copy_generation'; status: 'pending' | 'processing' | 'completed' | 'failed'
  source_asset_id: string; input_hash: string; is_current: boolean; provider: 'mock' | 'openai'; model: string
  facts: Facts; product_features: string | null; mood: string; use_address_for_copy: boolean; analysis_used: boolean
  warnings: string[]; error: { code: string; message: string } | null; review_required: boolean
  variants: { strategy: 'emotional' | 'price' | 'visual' | 'brand'; copy: { headline: string; body: string; cta: string } }[]
  attempts: { attempt: number; input_tokens: number | null; output_tokens: number | null; latency_seconds: number; estimated_cost_usd: number | null }[]
}
export async function copyState(handle: UploadHandle, start?: { asset: string; draft: Draft }): Promise<CopyState> {
  const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
  const response = await fetch(`${base}/jobs/${encodeURIComponent(handle.upload.job_id)}/copy-generation`, {
    method: start ? 'POST' : 'GET', headers: { 'X-Hanjang-Session': handle.token, ...(start ? { 'Content-Type': 'application/json' } : {}) },
    ...(start ? { body: JSON.stringify({ expected_asset_id: start.asset, expected_input: {
      facts: start.draft.facts, mood: start.draft.mood, product_features: start.draft.product_features ?? null,
      use_address_for_copy: start.draft.use_address_for_copy ?? false,
    } }) } : {}),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(body?.error?.message || '카피 생성 요청에 실패했습니다.')
  if (!body || body.operation !== 'copy_generation' || !['pending', 'processing', 'completed', 'failed'].includes(body.status)
    || !['mock', 'openai'].includes(body.provider) || typeof body.is_current !== 'boolean' || !Array.isArray(body.variants)
    || (body.status === 'completed' && (body.variants.length !== 4 || new Set(body.variants.map((v: { strategy: string }) => v.strategy)).size !== 4
      || body.variants.some((v: { strategy: string; copy: { headline: string; body: string; cta: string } }) => !['emotional', 'price', 'visual', 'brand'].includes(v.strategy)
        || !v.copy || typeof v.copy.headline !== 'string' || [...v.copy.headline].length < 1 || [...v.copy.headline].length > 60
        || typeof v.copy.body !== 'string' || [...v.copy.body].length > 160 || typeof v.copy.cta !== 'string' || [...v.copy.cta].length > 30)))) {
    throw new Error('카피 응답 형식이 올바르지 않습니다.')
  }
  return body
}
