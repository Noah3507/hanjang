import { ApiError, type UploadHandle } from './uploads'
import type { RenderState } from './rendering'

export interface Ranking {
  source: 'mock' | 'model' | 'fallback_mock'
  model_version: string
  feature_version: string | null
  revision: number
  items: { candidate_id: string; score: number; rank: number }[]
  pairwise: unknown | null
}
export interface RankingState {
  operation: 'ranking'; job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  revision: number | null; is_current: boolean; ranking: Ranking | null
  warnings: string[]; error: { code: string; message: string } | null
}

export async function rankingState(handle: UploadHandle, render?: RenderState): Promise<RankingState> {
  const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
  const response = await fetch(`${base}/jobs/${encodeURIComponent(handle.upload.job_id)}/ranking`, {
    method: render ? 'POST' : 'GET',
    headers: { 'X-Hanjang-Session': handle.token, ...(render ? { 'Content-Type': 'application/json' } : {}) },
    ...(render ? { body: JSON.stringify({ expected_render_revision: render.revision,
      expected_candidate_ids: render.candidates.map(c => c.candidate_id) }) } : {}),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(body?.error?.message || '임시 순위를 조회하지 못했습니다.')
  const r = body?.ranking as Ranking | null | undefined
  if (!body || body.operation !== 'ranking' || body.job_id !== handle.upload.job_id
    || !['pending', 'processing', 'completed', 'failed'].includes(body.status) || typeof body.is_current !== 'boolean'
    || (body.revision !== null && (!Number.isInteger(body.revision) || body.revision < 1))
    || !Array.isArray(body.warnings)
    || (body.status === 'completed' && !r)
    || (r && (!['mock', 'model', 'fallback_mock'].includes(r.source) || !r.model_version
      || r.revision !== body.revision || !Array.isArray(r.items) || r.items.length !== 4
      || new Set(r.items.map(i => i.candidate_id)).size !== 4
      || r.items.some((i, n) => !i.candidate_id || !Number.isFinite(i.score) || i.rank !== n+1
        || (n > 0 && (i.score > r.items[n-1].score || (i.score === r.items[n-1].score && i.candidate_id < r.items[n-1].candidate_id))))
      || (r.source !== 'model' && (r.model_version !== 'mock-v1' || r.feature_version !== null || r.pairwise != null))
      || (r.source === 'model' && !r.feature_version)))) {
    throw new Error('순위 응답 형식이 올바르지 않습니다.')
  }
  return body
}
