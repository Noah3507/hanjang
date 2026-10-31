import { ApiError, type Draft, type UploadHandle } from './uploads'
import type { RenderState } from './rendering'
export type AdCopy = { headline: string; body: string; cta: string }
export interface EditState {
 operation: 'editing'; status: 'pending'|'processing'|'completed'|'failed'; edit_id: string|null
 candidate_id: string|null; base_revision: number|null; target_revision: number|null
 is_current: boolean; error: {code:string;message:string}|null
}
const base=()=> (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/,'')
export async function editing(handle:UploadHandle,patch?:{candidate:string;copy:AdCopy;draft:Draft;render:RenderState}):Promise<EditState>{
 const url=`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}`
 const response=await fetch(patch?`${url}/candidates/${encodeURIComponent(patch.candidate)}`:`${url}/editing`,{
  method:patch?'PATCH':'GET',headers:{'X-Hanjang-Session':handle.token,...(patch?{'Content-Type':'application/json'}:{})},
  ...(patch?{body:JSON.stringify({expected_revision:patch.render.revision,expected_candidate_ids:patch.render.candidates.map(c=>c.candidate_id),
   expected_asset_id:patch.render.source_asset_id,expected_copy_key:patch.render.copy_key,
   expected_input:{facts:patch.draft.facts,mood:patch.draft.mood,product_features:patch.draft.product_features??null,use_address_for_copy:patch.draft.use_address_for_copy??false},copy:patch.copy})}:{})})
 const body=await response.json().catch(()=>null)
 if(!response.ok)throw new ApiError(body?.error?.message||'편집 요청에 실패했습니다.')
 if(!body||body.operation!=='editing'||!['pending','processing','completed','failed'].includes(body.status)||typeof body.is_current!=='boolean'
  ||body.status!=='pending'&&(!body.edit_id||!body.candidate_id||!Number.isInteger(body.base_revision)||!Number.isInteger(body.target_revision)))throw Error('편집 응답 형식이 올바르지 않습니다.')
 return body
}
export async function downloadAd(handle:UploadHandle,candidate:string,revision:number,format:'png'|'pdf'){
 const response=await fetch(`${base()}/jobs/${encodeURIComponent(handle.upload.job_id)}/candidates/${encodeURIComponent(candidate)}/download?format=${format}&expected_revision=${revision}`,{headers:{'X-Hanjang-Session':handle.token}})
 if(!response.ok){const body=await response.json().catch(()=>null);throw Error(body?.error?.message||'다운로드하지 못했습니다.')}
 if(!response.headers.get('Content-Type')?.startsWith(format==='png'?'image/png':'application/pdf'))throw Error('다운로드 형식이 올바르지 않습니다.')
 return response.blob()
}
