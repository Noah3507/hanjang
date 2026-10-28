export type Mood = 'warm' | 'minimal' | 'vivid' | 'premium'
export interface Facts {
  store_name: string
  product_name: string
  price_text: string
  address: string | null
  instagram_handle: string | null
}
export interface Upload {
  job_id: string; asset_id: string; width: number; height: number
  mime_type: 'image/jpeg' | 'image/png'; sha256: string
  created_at: string; expires_at: string
}
export interface Draft {
  job_id: string; status: 'pending'; facts: Facts; mood: Mood; expires_at: string
  product_features?: string | null; use_address_for_copy?: boolean
}
export interface UploadHandle { token: string; upload: Upload }
export class ApiError extends Error {
  constructor(message: string, public fields: { field: string; message: string }[] = []) { super(message) }
}
const base = () => (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

async function checked(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(body?.error?.message || '서버에 연결할 수 없습니다. 다시 시도해 주세요.', body?.error?.field_errors || [])
  }
  return response
}

function headers(token: string) { return { 'X-Hanjang-Session': token } }
export async function uploadPhoto(photo: File): Promise<UploadHandle> {
  const session = await (await checked(await fetch(`${base()}/sessions`, { method: 'POST' }))).json()
  const body = new FormData()
  body.append('photo', photo)
  const upload: Upload = await (await checked(await fetch(`${base()}/uploads`, { method: 'POST', headers: headers(session.session_token), body }))).json()
  return { token: session.session_token, upload }
}
export async function saveInput(handle: UploadHandle, facts: Facts, mood: Mood, extras?: { product_features: string | null; use_address_for_copy: boolean }): Promise<Draft> {
  return (await checked(await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/input`, {
    method: 'PUT', headers: { ...headers(handle.token), 'Content-Type': 'application/json' },
    body: JSON.stringify({ facts, mood, ...extras }),
  }))).json()
}
export async function getInput(handle: UploadHandle): Promise<Draft> {
  return (await checked(await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/input`, { headers: headers(handle.token) }))).json()
}
export async function getOriginal(handle: UploadHandle): Promise<Blob> {
  return (await checked(await fetch(`${base()}/assets/${encodeURIComponent(handle.upload.asset_id)}`, { headers: headers(handle.token) }))).blob()
}
