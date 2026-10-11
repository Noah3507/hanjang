export interface HealthResponse {
  status: 'ok'
  api_version: 'v1-draft'
}

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
  const response = await fetch(`${base}/health`, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error('백엔드 응답 오류')
  const data: unknown = await response.json()
  if (
    !data || typeof data !== 'object' ||
    !('status' in data) || data.status !== 'ok' ||
    !('api_version' in data) || data.api_version !== 'v1-draft'
  ) throw new Error('지원하지 않는 health 응답')
  return { status: data.status, api_version: data.api_version }
}
