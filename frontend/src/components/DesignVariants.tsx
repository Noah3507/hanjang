import {useEffect,useId,useRef,useState} from 'react'
import {createDesigns,getDesigns,rankDesigns,editDesign,downloadDesign,type Strategy,type DesignState,type Promotion} from '../api/designs'
import {preview,type RenderState} from '../api/rendering'
import type {UploadHandle} from '../api/uploads'
import type {AdCopy} from '../api/editing'
import {strategyLabels} from './AdResults'
import {storedStrategy,strategyStorageKey} from './strategyChoice'
import {currentDesignRanking,isTopDesignCloseCall,closeCallMessage} from './designRankingGuidance'

function Preview({handle,asset,label}:{handle:UploadHandle;asset:string;label:string}){
 const [url,setUrl]=useState(''),[error,setError]=useState('')
 useEffect(()=>{let dead=false,u='';setUrl('');setError('');void preview(handle,asset).then(b=>{if(!dead){u=URL.createObjectURL(b);setUrl(u)}}).catch(()=>{if(!dead)setError('이미지를 조회하지 못했습니다.')});return()=>{dead=true;if(u)URL.revokeObjectURL(u)}},[handle,asset])
 return url?<img src={url} alt={label} width="1080" height="1350"/>:<p role={error?'alert':'status'}>{error||'이미지 로딩 중'}</p>
}

export default function DesignVariants({handle,render,disabled,selectedStrategy,onSelectedStrategy,onEditingChange}:{handle:UploadHandle;render:RenderState;disabled:boolean;selectedStrategy?:Strategy;onSelectedStrategy?:(s:Strategy)=>void;onEditingChange?:(v:boolean)=>void}){
 const storage=strategyStorageKey(handle.upload.job_id)
 const formId=useId()
 const [strategy,setStrategy]=useState<Strategy>(()=>storedStrategy(handle.upload.job_id))
 const [state,setState]=useState<DesignState|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const emptyPromotion={original_price:'',discount_text:'',promotion_text:'',period_text:''}
 const [promotion,setPromotion]=useState<Promotion>(emptyPromotion)
 useEffect(()=>{if(selectedStrategy){sessionStorage.setItem(storage,selectedStrategy);setStrategy(selectedStrategy)}},[selectedStrategy,storage])
 const [editing,setEditing]=useState(''),[values,setValues]=useState<AdCopy>({headline:'',body:'',cta:''}),[price,setPrice]=useState('')
 useEffect(()=>{onEditingChange?.(Boolean(editing));return()=>onEditingChange?.(false)},[editing,onEditingChange])
 const ticket=useRef(0),region=useRef<HTMLElement>(null)
 const identity=JSON.stringify([handle.upload.job_id,strategy,render.revision,render.source_asset_id,render.copy_key,disabled])
 useEffect(()=>{const id=++ticket.current;setState(null);setEditing('');setError('');setBusy(false);setPromotion(emptyPromotion)
  if(!disabled)void run('get',id)
  return()=>{ticket.current++}
 // Source identity gates late responses, including job/strategy changes and v2 edits.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity])
 async function run(action:'get'|'create'|'rank'|'edit',id=++ticket.current){
  setBusy(true);setError('')
  try{
   const candidate=state?.candidates.find(c=>c.candidate_id===editing)
   let next=action==='create'?await createDesigns(handle,strategy,render,promotion):action==='rank'&&state?await rankDesigns(handle,strategy,state):action==='edit'&&state&&candidate?await editDesign(handle,strategy,state,candidate,values,price):await getDesigns(handle,strategy)
   for(let n=0;;n++){
    if(id!==ticket.current)return
    setState(next)
    if(next.promotion)setPromotion(next.promotion)
    if(next.status!=='processing'&&!next.editing)break
    if(n>=180)throw Error('처리가 계속 진행 중입니다. 상태 다시 조회를 눌러 주세요.')
    await new Promise(r=>setTimeout(r,1000));if(id!==ticket.current)return;next=await getDesigns(handle,strategy)
   }
   if(action==='edit'&&next.error)throw Error(next.error.message)
   if(action==='edit')setEditing('')
  }catch(e){if(id===ticket.current)setError(e instanceof Error?e.message:'시안 요청 오류')}
  finally{if(id===ticket.current)setBusy(false)}
 }
 function select(s:Strategy){setEditing('');sessionStorage.setItem(storage,s);setStrategy(s);onSelectedStrategy?.(s)}
 function cancelEdit(){const previous=editing;setEditing('');setTimeout(()=>{Array.from(region.current?.querySelectorAll<HTMLButtonElement>('button[data-edit-id]')||[]).find(b=>b.dataset.editId===previous)?.focus()},0)}
 async function download(id:string,format:'png'|'pdf'){
  if(!state)return;const c=state.candidates.find(c=>c.candidate_id===id);if(!c)return
  const token=++ticket.current;setBusy(true);setError('')
  try{const b=await downloadDesign(handle,strategy,state,c,format);if(token!==ticket.current)return
   const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=`한장-${c.template_id}-r${state.revision}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)
  }catch(e){if(token===ticket.current)setError(e instanceof Error?e.message:'다운로드 오류')}
  finally{if(token===ticket.current)setBusy(false)}
 }
 const stale=Boolean(state&&state.status!=='pending'&&(!state.is_current||disabled))
 const sourceMatches=state?.source_revision===render.revision&&state.source_asset_id===render.source_asset_id&&state.copy_key===render.copy_key
 const rankingDisabled=disabled||!sourceMatches
 const ranking=currentDesignRanking(state,rankingDisabled)
 const usable=Boolean(state?.status==='completed'&&state.is_current&&!disabled&&!busy&&!editing)
 const names:Record<string,string>={gallery:'갤러리',fade:'페이드',editorial:'에디토리얼',door:'문',circle:'원형컷',split:'상하분할','big-number':'빅넘버',stamp:'가격스탬프',wordmark:'워드마크',emblem:'엠블럼',pattern:'패턴','korean-wordmark':'국문워드마크','full-bleed':'풀블리드',polaroid:'폴라로이드',cinema:'시네마',film:'필름'}
 const ruleNames:Record<string,string>={contrast:'대비',font_size:'글자 크기',layout:'배치·겹침',density:'텍스트 밀도',subject_size:'피사체 크기',image_crop:'이미지 경계·가림'}
 const statuses:Record<string,string>={normal:'정상',caution:'주의',problem:'문제',unavailable:'측정 불가',complete:'측정 완료',partial:'일부 측정'}
 return <section ref={region} className="design-variants" aria-label="전략별 디자인 4종">
  <h3>마음에 드는 전략으로 디자인 4종 더 보기</h3>
  <p>위의 기존 4전략 광고는 유지됩니다. 각 전략의 네 디자인은 같은 문구로 비교합니다.</p>
  <div className="strategy-choices" role="group" aria-label="디자인 전략 선택">{(['emotional','price','visual','brand'] as Strategy[]).map(s=><button type="button" key={s} aria-pressed={strategy===s} disabled={disabled||Boolean(editing)} onClick={()=>select(s)}>{strategyLabels[s]} 전략 선택</button>)}</div>
  <p>선택 전략: <strong>{strategyLabels[strategy]}</strong></p>
  <button type="button" onClick={()=>region.current?.closest('.ad-rendering')?.scrollIntoView({block:'start',behavior:'smooth'})}>기존 4전략 광고로 돌아가기</button>
  <details><summary>직접 확인한 행사 정보 입력 (선택)</summary><p>입력하지 않은 할인·행사·기간은 생성하지 않습니다. 완료된 시안의 행사 정보는 보존됩니다. 할인율은 입력한 소수 자릿수에서 반올림해 비교합니다.</p>{(['original_price','discount_text','promotion_text','period_text'] as const).map((f,i)=><label key={f}>{['할인 전 가격','할인율 (예: 30%)','행사명','행사 기간 (예: 2026.11.16–2026.11.20)'][i]}<input maxLength={f==='discount_text'?10:40} disabled={disabled||busy||state?.status==='completed'} value={promotion[f]} onChange={e=>setPromotion(v=>({...v,[f]:e.target.value}))}/></label>)}</details>
  <button disabled={disabled||busy||Boolean(editing)} onClick={()=>void run('create')}>이 전략으로 시안 4개 더 보기</button>{' '}
  <button disabled={disabled||busy||Boolean(editing)} onClick={()=>void run('get')}>시안 상태 다시 조회</button>
  <p role="status">시안 상태: {state?.status||'pending'} · revision {state?.revision||0}{busy?' · 처리 중':''}</p>
  {stale&&<p role="alert">이전 입력의 시안입니다. 최신 결과로 다시 생성해 주세요.</p>}
  {error&&<p role="alert">{error}</p>}{state?.error&&<p role="alert">{state.error.message}</p>}
  {state?.status==='failed'&&<p>{state.failed_templates?.length?`일부 시안 생성 실패: ${state.failed_templates.join(', ')}. 네 시안의 게시를 보류했습니다.`:'전체 시안을 생성하지 못했습니다.'} 입력 길이를 확인하고 다시 생성해 주세요. 기존 v2 광고는 유지됩니다.</p>}
  {state?.status==='completed'&&<>
   <p>v3 revision {state.revision} · {state.mock_copy?'Mock 카피':'기존 실제 카피 재사용'} · 추가 LLM 호출 없음</p>
   <button disabled={!usable} onClick={()=>void run('rank')}>시안 ML 참고 순위 계산</button>
   <p>같은 전략의 디자인에 대한 모델 성능은 별도 검증되지 않았습니다. 점수는 전환율·구매율·객관적 품질이 아니며 진단과 합산하지 않습니다. A~D 순서를 유지합니다.</p>
   {state.ranking_status==='processing'&&<p role="status">모델 평가 중</p>}
   {state.ranking_error&&<p role="alert">{state.ranking_error.message}</p>}
   {state.ranking?.source==='mock'&&<p>시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다.</p>}
   {isTopDesignCloseCall(state,rankingDisabled)&&<p role="note">{closeCallMessage}</p>}
   <div className="ad-cards">{state.candidates.map(c=>{const rank=ranking?.items.find(i=>i.candidate_id===c.candidate_id);const diagnostic=state.diagnostics.find(d=>d.candidate_id===c.candidate_id);return <article key={c.candidate_id} aria-label={`${c.template_id} 시안`}>
    <h4>{c.template_id.split('_')[1].toUpperCase()} · {names[c.design_name]||c.design_name}</h4>
    <Preview handle={handle} asset={c.png.asset_id} label={`${strategyLabels[strategy]} ${c.template_id} 광고`}/>
    <p>{c.copy?.headline}</p><p>가격: {c.facts?.price_text} · 편집 {c.edit_revision}회</p>
    {rank&&<p>{rank.rank}위 {ranking?.source==='model'?`· 상대 선호 score ${rank.score.toFixed(2)} · ${ranking.model_version}`:'· 시연용'}</p>}
    <details><summary>가독성 진단 · {statuses[diagnostic?.coverage||'unavailable']}</summary><ul>{diagnostic?.rules.map(r=><li key={r.rule_id}>{ruleNames[r.rule_id]||r.rule_id}: {statuses[r.status]||r.status} · {r.explanation}</li>)}</ul><p>의도된 사진·장식 겹침도 경고를 유지합니다. 미측정 대비는 정상 판정하지 않습니다.</p></details>
    <button data-edit-id={c.candidate_id} disabled={!usable||!c.copy} onClick={()=>{setEditing(c.candidate_id);setValues({...c.copy!});setPrice(c.facts?.price_text||'');setError('')}}>시안 {c.template_id.split('_')[1].toUpperCase()} 편집</button>{' '}
    <button disabled={!usable} onClick={()=>void download(c.candidate_id,'png')}>시안 PNG 다운로드</button>{' '}
    <button disabled={!usable} onClick={()=>void download(c.candidate_id,'pdf')}>시안 PDF 다운로드</button>
   </article>})}</div>
  </>}
  {editing&&<form aria-label="v3 시안 편집" onSubmit={e=>{e.preventDefault();void run('edit')}}>
   <h4>선택 시안 {state?.candidates.find(c=>c.candidate_id===editing)?.template_id} 편집</h4><p>가격은 이 시안만 변경합니다. 원래 상품 정보와 v2 광고는 보존됩니다. 할인·본문과 가격이 일치하는지 확인해 주세요.</p>
   {(['headline','body','cta'] as const).map((f,i)=><div key={f}><label htmlFor={`${formId}-${f}`}>v3 {['제목','본문','CTA'][i]}</label><textarea id={`${formId}-${f}`} autoFocus={i===0} required={f==='headline'} maxLength={[60,160,30][i]} disabled={busy||stale||disabled} value={values[f]} onChange={e=>setValues(v=>({...v,[f]:e.target.value}))}/></div>)}
   <label htmlFor={`${formId}-price`}>v3 가격</label><input id={`${formId}-price`} required maxLength={40} disabled={busy||stale||disabled} value={price} onChange={e=>setPrice(e.target.value)}/>
   <button disabled={busy||stale||disabled}>시안 적용하고 재렌더링</button>{' '}<button type="button" disabled={busy} onClick={cancelEdit}>시안 편집 취소</button>
  </form>}
 </section>
}
