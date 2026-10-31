import {useEffect,useId,useRef,useState} from 'react'
import {editing,downloadAd,type AdCopy,type EditState} from '../api/editing'
import type {Draft,UploadHandle} from '../api/uploads'
import type {RenderState} from '../api/rendering'
import {strategyLabels} from './AdResults'

export default function AdEditor({handle,draft,render,disabled,onApplied,onBusy}:{handle:UploadHandle;draft:Draft;render:RenderState;disabled:boolean;onApplied:()=>void;onBusy:(busy:boolean)=>void}){
 const [selected,setSelected]=useState(render.candidates[0]?.candidate_id??'')
 const editorId=useId()
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const [values,setValues]=useState<AdCopy>({headline:'',body:'',cta:''}),[state,setState]=useState<EditState|null>(null)
 const ticket=useRef(0),editButton=useRef<HTMLButtonElement>(null)
 const callbacks=useRef({onApplied,onBusy});callbacks.current={onApplied,onBusy}
 const candidate=render.candidates.find(c=>c.candidate_id===selected)??render.candidates[0]
 const identity=JSON.stringify([handle.upload.job_id,render.revision,render.source_asset_id,render.copy_key,disabled,draft])
 function working(value:boolean){setBusy(value);callbacks.current.onBusy(value)}
 async function poll(first:EditState,id:number){let next=first;for(let n=0;;n++){
  if(id!==ticket.current)return;setState(next)
  if(next.status!=='processing')return next
  if(n>=120)throw Error('편집 조회 시간이 초과됐습니다. 상태를 다시 조회해 주세요.')
  await new Promise(r=>setTimeout(r,1000));if(id!==ticket.current)return;next=await editing(handle)
 }}
 useEffect(()=>{const id=++ticket.current;setOpen(false);setError('');setState(null);working(false)
  if(!disabled)void editing(handle).then(async next=>{
   if(id!==ticket.current)return
   if(next.status==='processing')working(true)
   const done=await poll(next,id)
   if(id===ticket.current&&done?.status==='completed'&&done.is_current&&(done.target_revision??0)>render.revision)callbacks.current.onApplied()
  }).catch(e=>{if(id===ticket.current)setError(e instanceof Error?e.message:'편집 조회 오류')}).finally(()=>{if(id===ticket.current)working(false)})
  return()=>{ticket.current++;callbacks.current.onBusy(false)}
 // identity contains the complete UI source snapshot; callbacks are refs.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity])
 function begin(){if(!candidate?.copy)return;setValues({...candidate.copy});setError('');setOpen(true)}
 function cancel(){setOpen(false);setError('');setTimeout(()=>editButton.current?.focus(),0)}
 async function apply(){if(!candidate)return;const id=++ticket.current;working(true);setError('')
  try{const done=await poll(await editing(handle,{candidate:candidate.candidate_id,copy:values,draft,render}),id)
   if(id!==ticket.current)return
   if(done?.status==='completed'){setOpen(false);callbacks.current.onApplied()}
  }catch(e){if(id===ticket.current)setError(e instanceof Error?e.message:'편집 오류')}
  finally{if(id===ticket.current)working(false)}
 }
 async function download(format:'png'|'pdf'){if(!candidate)return;const id=++ticket.current;working(true);setError('')
  try{const blob=await downloadAd(handle,candidate.candidate_id,render.revision,format);if(id!==ticket.current)return
   const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`한장-${candidate.strategy}-r${render.revision}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
  }catch(e){if(id===ticket.current)setError(e instanceof Error?e.message:'다운로드 오류')}
  finally{if(id===ticket.current)working(false)}
 }
 if(!candidate)return null
 const changed=candidate.copy&&JSON.stringify(values)!==JSON.stringify(candidate.copy)
 return <section aria-label="광고 편집 및 다운로드" className="ad-editor">
  <h3>광고 편집 및 다운로드 · revision {render.revision}</h3>
  <label>수정할 광고<select value={candidate.candidate_id} disabled={busy||open||disabled} onChange={e=>setSelected(e.target.value)}>{render.candidates.map(c=><option key={c.candidate_id} value={c.candidate_id}>{strategyLabels[c.strategy]}</option>)}</select></label>
  <p>현재 성공본: {candidate.copy?.headline??'문구 조회 불가'}</p>
  <button ref={editButton} disabled={disabled||busy||open||!candidate.copy} onClick={begin}>문구 편집</button>{' '}
  <button disabled={disabled||busy||open} onClick={()=>void download('png')}>PNG 다운로드</button>{' '}
  <button disabled={disabled||busy||open} onClick={()=>void download('pdf')}>A4 PDF 다운로드</button>
  <p>A4는 선택 광고 한 장을 담은 래스터 PDF입니다. 검색 가능한 텍스트나 300dpi 인쇄 원본이 아닙니다.</p>
  {open&&<form aria-label={`${strategyLabels[candidate.strategy]} 광고 문구 편집`} onSubmit={e=>{e.preventDefault();void apply()}}>
   <p>가게명: {draft.facts.store_name} · 상품명: {draft.facts.product_name} · 가격: {draft.facts.price_text}</p>
   <p>주소: {draft.facts.address||'없음'} · Instagram: {draft.facts.instagram_handle||'없음'} (읽기 전용)</p>
   <p>사실 정보 변경은 상품 입력 화면에서 저장해 주세요. 문구는 사용자가 작성하며 사실을 확인해 주세요.</p>
   {(['headline','body','cta'] as const).map((field,i)=><div key={field}><label htmlFor={`${editorId}-${field}`}>{['제목','본문','CTA'][i]}</label><textarea id={`${editorId}-${field}`} autoFocus={i===0} rows={2} required={field==='headline'} maxLength={[60,160,30][i]} value={values[field]} disabled={busy||disabled} onChange={e=>setValues(v=>({...v,[field]:e.target.value}))}/></div>)}
   <button type="submit" disabled={disabled||busy||!changed||!values.headline.trim()}>적용하고 재렌더링</button>{' '}
   <button type="button" disabled={busy} onClick={cancel}>편집 취소</button>
  </form>}
  {busy&&<p role="status">편집 또는 다운로드 처리 중입니다. 마지막 성공본은 유지됩니다.</p>}
  {state&&state.status!=='pending'&&<p role="status">편집 상태: {state.status}{!state.is_current?' · 이전 snapshot':''}</p>}
  {state?.error&&<p role="alert">{state.error.message}</p>}{error&&<p role="alert">{error}</p>}
 </section>
}
