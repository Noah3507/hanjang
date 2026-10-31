import {useEffect,useRef,useState} from 'react'
import {diagnostics,type DiagnosticRule,type DiagnosticsState} from '../api/diagnostics'
import type {RenderState} from '../api/rendering'
import type {UploadHandle} from '../api/uploads'
import {strategyLabels} from './AdResults'
const labels={contrast:'명도 대비',font_size:'글자 크기',layout:'경계·겹침',density:'텍스트 블록 밀도'}
const statuses={normal:'정상',caution:'주의',problem:'문제',unavailable:'측정 불가'}
const coverages={complete:'측정 항목 확인',partial:'일부 측정 불가',unavailable:'측정 불가'}
const fields:Record<string,string>={headline:'제목',body:'본문',cta:'CTA',store_name:'가게명',product_name:'상품명',price_text:'가격',address:'주소',instagram_handle:'Instagram'}
function items(rule:DiagnosticRule){return Array.isArray(rule.measured_value?.items)?rule.measured_value.items.filter(x=>x&&typeof x==='object') as Record<string,unknown>[]:[]}
function value(rule:DiagnosticRule){
 const v=rule.measured_value;if(!v)return '측정값 없음'
 if(rule.rule_id==='contrast')return typeof v.minimum==='number'?`확인된 최소 대비 ${v.minimum.toFixed(4)}:1 (판정은 반올림 전)`:'대비 측정값 없음'
 if(rule.rule_id==='font_size')return typeof v.minimum==='number'?`확인된 최소 글자 ${v.minimum} PNG px`:'크기 측정값 없음'
 if(rule.rule_id==='density')return typeof v.ratio==='number'?`확인된 텍스트 블록 영역 비율 ${(v.ratio*100).toFixed(1)}%${v.missing_boxes?' (누락 영역 제외·하한값)':''} · 가독성 점수가 아닙니다`:'영역 비율 측정값 없음'
 return `캔버스 이탈 ${Array.isArray(v.out_of_bounds)?v.out_of_bounds.length:'미확인'}개 · bbox 교차는 의도적인 배치인지 확정하지 않습니다`
}
export default function ReadabilityDiagnostics({handle,render,disabled}:{handle:UploadHandle;render:RenderState;disabled:boolean}){
 const [state,setState]=useState<DiagnosticsState|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const ticket=useRef(0)
 const snapshot=JSON.stringify([handle.upload.job_id,render.revision,render.source_asset_id,render.copy_key,render.candidates.map(c=>[c.candidate_id,c.png.asset_id]),disabled])
 useEffect(()=>{const id=++ticket.current;setState(null);setError('');setBusy(false);if(!disabled)void update(false,id);return()=>{ticket.current++}
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[snapshot])
 async function update(start:boolean,id=++ticket.current){setBusy(true);setError('')
  try{let next=await diagnostics(handle,start?render:undefined)
   for(let n=0;;n++){
    if(id!==ticket.current)return;setState(next)
    if(next.status!=='processing')break
    if(n>=120)throw Error('진단 재조회 시간이 초과됐습니다. 다시 조회해 주세요.')
    await new Promise(r=>setTimeout(r,1000));if(id!==ticket.current)return;next=await diagnostics(handle)
   }
  }catch(e){if(id===ticket.current){setState(null);setError(e instanceof Error?e.message:'진단 오류')}}
  finally{if(id===ticket.current)setBusy(false)}
 }
 const current=state?.status==='completed'&&state.is_current&&state.revision===render.revision&&state.results.every(c=>render.candidates.some(r=>r.candidate_id===c.candidate_id&&r.png.asset_id===c.asset_id))&&!disabled
 const stale=state&&state.status!=='pending'&&(!state.is_current||state.revision!==render.revision||state.status==='completed'&&!current)
 return <section aria-label="규칙 기반 가독성 진단" className="readability-diagnostics">
  <h3>규칙 기반 가독성 진단</h3>
  <p>광고 선호도 순위와 별개입니다. 성과·CTR·구매율·실제 시선이나 종합 가독성 점수를 측정하지 않습니다.</p>
  <button type="button" disabled={disabled||busy} onClick={()=>void update(true)}>가독성 진단 실행</button>{' '}
  <button type="button" disabled={disabled||busy} onClick={()=>void update(false)}>진단 다시 조회</button>
  <p role="status">{busy?'가독성 진단 요청 처리 중':`진단 상태: ${state?.status??'조회 중'}`}</p>
  {state?.status==='pending'&&!busy&&<p>아직 진단 결과가 없습니다. 최신 성공 광고를 진단해 주세요.</p>}
  {stale&&<p role="alert">이전 revision 또는 snapshot의 진단입니다. 최신 성공 광고로 다시 진단해 주세요.</p>}
  {error&&<p role="alert">{error}</p>}{state?.error&&<p role="alert">{state.error.message}</p>}
  {current&&<><p>진단 revision: {state.revision} · 기준 {state.rules_version}</p><div className="diagnostic-cards">{state.results.map(c=><article key={c.candidate_id} aria-label={`${strategyLabels[c.strategy]} 가독성 진단`}>
   <h4>{strategyLabels[c.strategy]} · {coverages[c.coverage]}</h4>
   {c.rules.map(r=><div key={r.rule_id} className="diagnostic-rule"><h5>{labels[r.rule_id as keyof typeof labels]} · {statuses[r.status]}</h5>
    <p>{value(r)}</p>{r.coverage!=='complete'&&<p>{coverages[r.coverage]} — 정상 판정과 다릅니다.</p>}
    <details><summary>판단 근거와 조치</summary><p>기준: {r.criterion}</p><p>{r.explanation}</p>
     {items(r).length>0&&<ul>{items(r).map((item,i)=><li key={i}>{fields[String(item.field)]??String(item.field)}: {statuses[item.status as keyof typeof statuses]??'측정 불가'} · {typeof item.value==='number'?item.value.toFixed(r.rule_id==='contrast'?4:1):'측정값 없음'} {r.unit}{typeof item.threshold==='number'?` / 기준 ${item.threshold}:1`:''}</li>)}</ul>}
     <p>{r.action}</p></details>
   </div>)}
  </article>)}</div><p>진단은 PNG나 문구를 자동 수정하지 않습니다. 위 문구 편집에서 수정 후 재렌더링·재진단할 수 있습니다.</p></>}
 </section>
}
