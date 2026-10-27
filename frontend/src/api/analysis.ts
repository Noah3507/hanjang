import { ApiError, type UploadHandle } from './uploads'

export interface AnalysisState {
  job_id: string; operation: 'photo_analysis'; status: 'pending' | 'processing' | 'completed' | 'failed'
  status_url: string; source_asset_id: string; photo_source: 'original' | 'processed'; is_current: boolean
  analysis_version: string; expires_at: string; warnings: string[]; error: { code: string; message: string } | null
  clip: { status: 'available' | 'unavailable'; score_type: 'cosine_similarity'; model_version: string; prompt_version: string
    cues: { category: string; candidate_id: string; label: string; similarity: number }[] }
  palette: { status: 'available' | 'unavailable'; colors: { hex: string; rgb: number[]; proportion: number }[] }
}
export async function analysisState(handle: UploadHandle, asset?: string): Promise<AnalysisState> {
  const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
  const response = await fetch(`${base}/jobs/${encodeURIComponent(handle.upload.job_id)}/photo-analysis`, {
    method: asset ? 'POST' : 'GET',
    headers: { 'X-Hanjang-Session': handle.token, ...(asset ? { 'Content-Type': 'application/json' } : {}) },
    ...(asset ? { body: JSON.stringify({ expected_asset_id: asset }) } : {}),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(body?.error?.message || '사진 분석 요청에 실패했습니다.')
  if (!body || !['pending', 'processing', 'completed', 'failed'].includes(body.status)
    || body.operation !== 'photo_analysis' || typeof body.is_current !== 'boolean'
    || !Array.isArray(body.clip?.cues) || !Array.isArray(body.palette?.colors)
    || body.clip.cues.some((cue: { similarity: number }) => !Number.isFinite(cue.similarity) || Math.abs(cue.similarity) > 1)
    || body.palette.colors.some((color: { hex: string; proportion: number }) => !/^#[0-9A-F]{6}$/.test(color.hex) || !Number.isFinite(color.proportion) || color.proportion <= 0 || color.proportion > 1)) {
    throw new Error('사진 분석 응답 형식이 올바르지 않습니다.')
  }
  return body
}
