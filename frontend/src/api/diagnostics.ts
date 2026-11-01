import {ApiError,type UploadHandle} from './uploads'
import type {RenderState} from './rendering'
export type RuleStatus='normal'|'caution'|'problem'|'unavailable'
export type Coverage='complete'|'partial'|'unavailable'
export interface DiagnosticRule{rule_id:string;status:RuleStatus;coverage:Coverage;measured_value:Record<string,unknown>|null;unit:string;criterion:string;explanation:string;action:string}
export interface DiagnosticCandidate{candidate_id:string;strategy:'emotional'|'price'|'visual'|'brand';asset_id:string;coverage:Coverage;rules:DiagnosticRule[]}
export interface DiagnosticsState{job_id:string;operation:'diagnostics';status:'pending'|'processing'|'completed'|'failed';revision:number|null;is_current:boolean;rules_version:string;results:DiagnosticCandidate[];warnings:string[];error:{code:string;message:string}|null}
function coverage(v:unknown){return ['complete','partial','unavailable'].includes(String(v))}
function finite(v:unknown):boolean{
 if(typeof v==='number')return Number.isFinite(v)
 if(Array.isArray(v))return v.every(finite)
 if(v&&typeof v==='object')return Object.values(v).every(finite)
 return v===null||['string','boolean'].includes(typeof v)
}
export async function diagnostics(handle:UploadHandle,render?:RenderState):Promise<DiagnosticsState>{
 const base=(import.meta.env.VITE_API_BASE_URL||'/api/v1').replace(/\/$/,'')
 const response=await fetch(`${base}/jobs/${encodeURIComponent(handle.upload.job_id)}/diagnostics`,{method:render?'POST':'GET',headers:{'X-Hanjang-Session':handle.token,...(render?{'Content-Type':'application/json'}:{})},
  ...(render?{body:JSON.stringify({expected_render_revision:render.revision,expected_candidates:render.candidates.map(c=>({candidate_id:c.candidate_id,asset_id:c.png.asset_id}))})}:{})})
 const b=await response.json().catch(()=>null)
 if(!response.ok)throw new ApiError(b?.error?.message||'가독성 진단에 실패했습니다.')
 if(!b||b.job_id!==handle.upload.job_id||b.operation!=='diagnostics'||!['pending','processing','completed','failed'].includes(b.status)||typeof b.is_current!=='boolean'
  ||(b.revision!==null&&(!Number.isInteger(b.revision)||b.revision<1))||!b.rules_version||!Array.isArray(b.results)||!Array.isArray(b.warnings)
  ||(b.status==='completed'&&(b.results.length!==4||new Set(b.results.map((r:DiagnosticCandidate)=>r?.candidate_id)).size!==4||new Set(b.results.map((r:DiagnosticCandidate)=>r?.asset_id)).size!==4||new Set(b.results.map((r:DiagnosticCandidate)=>r?.strategy)).size!==4))
  ||b.results.some((r:DiagnosticCandidate)=>!r||!r.candidate_id||!r.asset_id||!['emotional','price','visual','brand'].includes(r.strategy)||!coverage(r.coverage)||!Array.isArray(r.rules)||r.rules.length!==4||new Set(r.rules.map(x=>x?.rule_id)).size!==4||r.rules.some(x=>!x||!['contrast','font_size','layout','density'].includes(x.rule_id)||!['normal','caution','problem','unavailable'].includes(x.status)||!coverage(x.coverage)||!x.criterion||!x.explanation||!x.action||!finite(x.measured_value))))throw Error('가독성 진단 응답 형식이 올바르지 않습니다.')
 return b
}
