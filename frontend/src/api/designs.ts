import {ApiError,type UploadHandle} from './uploads'
import type {RenderCandidate,RenderState} from './rendering'
import type {AdCopy} from './editing'
export type Strategy=RenderCandidate['strategy']
export interface Promotion {original_price:string;discount_text:string;promotion_text:string;period_text:string}
export interface DesignCandidate extends RenderCandidate {template_id:string;design_name:string;generation_revision:number;edit_revision:number;original_price_text:string}
export interface DesignState {
 operation:'designs_v3';strategy:Strategy;status:'pending'|'processing'|'completed'|'failed';revision:number;source_revision:number
 source_asset_id:string;copy_key:string|null;template_version:string;is_current:boolean;editing:boolean;snapshot:string|null;mock_copy:boolean
 candidates:DesignCandidate[];diagnostics:{candidate_id:string;coverage:string;rules:{rule_id:string;status:string;coverage:string;explanation:string}[]}[]
 ranking:{source:'model'|'mock'|'fallback_mock';model_version:string;revision?:number;items:{candidate_id:string;rank:number;score:number}[]}|null
 ranking_close_call_score_gap?:number|null
 ranking_status:string;ranking_error:{code:string;message:string}|null;error:{code:string;message:string}|null
 failed_templates?:string[];failed_fields?:string[]
 promotion?:Promotion
}
const base=()=> (import.meta.env.VITE_API_BASE_URL||'/api/v1').replace(/\/$/,'')
function url(h:UploadHandle,s:Strategy){return `${base()}/jobs/${encodeURIComponent(h.upload.job_id)}/designs/${s}`}
async function request(h:UploadHandle,s:Strategy,method='GET',body?:unknown,suffix=''):Promise<DesignState>{
 const r=await fetch(url(h,s)+suffix,{method,headers:{'X-Hanjang-Session':h.token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})})
 const b=await r.json().catch(()=>null)
 if(!r.ok)throw new ApiError(b?.error?.message||'시안 요청에 실패했습니다.')
 if(!b||b.operation!=='designs_v3'||b.strategy!==s||typeof b.is_current!=='boolean'||typeof b.mock_copy!=='boolean'||!Array.isArray(b.candidates)||!['pending','processing','completed','failed'].includes(b.status)
  ||(b.status==='completed'&&(b.candidates.length!==4||new Set(b.candidates.map((c:DesignCandidate)=>c.candidate_id)).size!==4
   ||!(/^[a-f0-9]{64}$/.test(b.snapshot||''))||new Set(b.candidates.map((c:DesignCandidate)=>c.template_id)).size!==4||b.candidates.some((c:DesignCandidate)=>c.strategy!==s||c.revision!==b.revision||!c.png||c.png.revision!==b.revision||!/^[a-f0-9]{32}$/.test(c.png.asset_id)||c.png.width!==1080||c.png.height!==1350||!new RegExp(`^${s}_[abcd]$`).test(c.template_id)))))throw Error('시안 응답이 올바르지 않습니다.')
 return b
}
export function getDesigns(h:UploadHandle,s:Strategy){return request(h,s)}
export function createDesigns(h:UploadHandle,s:Strategy,render:RenderState,promotion?:Promotion){return request(h,s,'POST',{
 expected_render_revision:render.revision,expected_source_asset_id:render.source_asset_id,expected_copy_key:render.copy_key,...(promotion?{promotion}:{})})}
function snapshot(state:DesignState){return {expected_revision:state.revision,expected_snapshot:state.snapshot}}
export function rankDesigns(h:UploadHandle,s:Strategy,state:DesignState){return request(h,s,'POST',snapshot(state),'/ranking')}
export function editDesign(h:UploadHandle,s:Strategy,state:DesignState,c:DesignCandidate,copy:AdCopy,price:string){return request(h,s,'PATCH',{
 ...snapshot(state),expected_asset_id:c.png.asset_id,copy,price_text:price},`/candidates/${encodeURIComponent(c.candidate_id)}`)}
export async function downloadDesign(h:UploadHandle,s:Strategy,state:DesignState,c:DesignCandidate,format:'png'|'pdf'){
 const params=new URLSearchParams({format,expected_revision:String(state.revision),expected_snapshot:state.snapshot||''})
 const r=await fetch(url(h,s)+`/candidates/${encodeURIComponent(c.candidate_id)}/download?${params}`,{headers:{'X-Hanjang-Session':h.token}})
 if(!r.ok){const b=await r.json().catch(()=>null);throw Error(b?.error?.message||'다운로드하지 못했습니다.')}
 if(!r.headers.get('Content-Type')?.startsWith(format==='png'?'image/png':'application/pdf'))throw Error('다운로드 형식이 올바르지 않습니다.')
 return r.blob()
}
