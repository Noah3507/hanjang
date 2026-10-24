import { ApiError, type UploadHandle } from './uploads'

export interface PhotoAsset { asset_id: string; width: number; height: number; mime_type: string; sha256: string }
export interface PhotoState {
  job_id: string; operation: 'photo_processing'; status: 'pending' | 'processing' | 'completed' | 'failed'
  original: PhotoAsset; processed: PhotoAsset | null; photo_source: 'original' | 'processed'
  warnings: string[]; expires_at: string
}
const base = () => (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
async function checked(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(body?.error?.message || '사진 처리 상태를 확인할 수 없습니다.')
  }
  return response
}
export async function photoState(handle: UploadHandle, start = false): Promise<PhotoState> {
  return (await checked(await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/photo-processing`, {
    method: start ? 'POST' : 'GET', headers: { 'X-Hanjang-Session': handle.token },
  }))).json()
}
export async function choosePhoto(handle: UploadHandle, photo_source: 'original' | 'processed'): Promise<PhotoState> {
  return (await checked(await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/photo-source`, {
    method: 'PUT', headers: { 'X-Hanjang-Session': handle.token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_source }),
  }))).json()
}
export async function photoBlob(handle: UploadHandle, asset: string): Promise<Blob> {
  return (await checked(await fetch(`${base()}/assets/${encodeURIComponent(asset)}`, {
    headers: { 'X-Hanjang-Session': handle.token },
  }))).blob()
}
