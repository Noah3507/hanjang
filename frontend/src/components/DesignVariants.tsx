import {useEffect,useId,useRef,useState} from 'react'
import {createDesigns,getDesigns,rankDesigns,editDesign,downloadDesign,type Strategy,type DesignState,type Promotion} from '../api/designs'
import type {RenderState} from '../api/rendering'
import {useAssetUrls} from './useAssetUrls'
import type {UploadHandle} from '../api/uploads'
import type {AdCopy} from '../api/editing'
import {strategyLabels} from './AdResults'
import {storedStrategy,strategyStorageKey} from './strategyChoice'
import {currentDesignRanking,isTopDesignCloseCall,closeCallMessage} from './designRankingGuidance'

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
    // While one design is being redrawn, keep showing the four finished ones instead of an empty carousel.
    if(!(action==='edit'&&next.status==='processing'))setState(next)
    if(next.promotion)setPromotion(next.promotion)
    if(next.status!=='processing'&&!next.editing)break
    if(n>=180)throw Error('처리가 계속 진행 중입니다. 상태 다시 조회를 눌러 주세요.')
    await new Promise(r=>setTimeout(r,1000));if(id!==ticket.current)return;next=await getDesigns(handle,strategy)
   }
   if(action==='edit'&&next.error)throw Error(next.error.message)
   if(action==='edit'){const done=editing;setEditing('');focusEdit(done)}
  }catch(e){if(id===ticket.current)setError(e instanceof Error?e.message:'시안 요청 오류')}
  finally{if(id===ticket.current)setBusy(false)}
 }
 function select(s:Strategy){setEditing('');sessionStorage.setItem(storage,s);setStrategy(s);onSelectedStrategy?.(s)}
 // Closing the form shortens the page, so bring the edited design back into view before focusing its button.
 function focusEdit(id:string){setTimeout(()=>{
  const index=state?.candidates.findIndex(c=>c.candidate_id===id)??-1
  if(index>=0)go(index)
  const wrap=track.current?.closest('.carousel-wrap');if(wrap&&typeof wrap.scrollIntoView==='function')wrap.scrollIntoView({block:'start'})
  Array.from(region.current?.querySelectorAll<HTMLButtonElement>('button[data-edit-id]')||[]).find(b=>b.dataset.editId===id)?.focus({preventScroll:true})},0)}
 function cancelEdit(){const previous=editing;setEditing('');setError('');focusEdit(previous)}
 async function download(id:string,format:'png'|'pdf'){
  if(!state)return;const c=state.candidates.find(c=>c.candidate_id===id);if(!c)return
  const token=++ticket.current;setBusy(true);setError('')
  try{const b=await downloadDesign(handle,strategy,state,c,format);if(token!==ticket.current)return
   const u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=`한장-${c.template_id}-r${state.revision}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)
  }catch(e){if(token===ticket.current)setError(e instanceof Error?e.message:'다운로드 오류')}
  finally{if(token===ticket.current)setBusy(false)}
 }
 const urls=useAssetUrls(handle,state?.status==='completed'?state.candidates.map(c=>c.png.asset_id):[])
 const [active,setActive]=useState(0),track=useRef<HTMLDivElement>(null)
 useEffect(()=>{setActive(0)},[strategy])
 function go(i:number){
  const t=track.current,el=t?.children[i] as HTMLElement|undefined;if(!t||!el)return
  setActive(i);if(typeof t.scrollTo==='function')t.scrollTo({left:el.offsetLeft-(t.clientWidth-el.clientWidth)/2,behavior:'smooth'})
 }
 function sync(){
  const t=track.current;if(!t)return
  const middle=t.scrollLeft+t.clientWidth/2;let best=0,distance=Infinity
  Array.from(t.children).forEach((el,i)=>{const e=el as HTMLElement,d=Math.abs(e.offsetLeft+e.clientWidth/2-middle);if(d<distance){distance=d;best=i}})
  setActive(best)
 }
 async function downloadAll(){if(!state)return;for(const c of state.candidates)await download(c.candidate_id,'png')}
 const stale=Boolean(state&&state.status!=='pending'&&(!state.is_current||disabled))
 const sourceMatches=state?.source_revision===render.revision&&state.source_asset_id===render.source_asset_id&&state.copy_key===render.copy_key
 const rankingDisabled=disabled||!sourceMatches
 const ranking=currentDesignRanking(state,rankingDisabled)
 const usable=Boolean(state?.status==='completed'&&state.is_current&&!disabled&&!busy&&!editing)
 const names:Record<string,string>={gallery:'갤러리',fade:'페이드',editorial:'에디토리얼',door:'문',circle:'원형컷',split:'상하분할','big-number':'빅넘버',stamp:'가격스탬프',wordmark:'워드마크',emblem:'엠블럼',pattern:'패턴','korean-wordmark':'국문워드마크','full-bleed':'풀블리드',polaroid:'폴라로이드',cinema:'시네마',film:'필름'}
 const ruleNames:Record<string,string>={contrast:'대비',font_size:'글자 크기',layout:'배치·겹침',density:'텍스트 밀도',subject_size:'피사체 크기',image_crop:'이미지 경계·가림'}
 const statuses:Record<string,string>={normal:'정상',caution:'주의',problem:'문제',unavailable:'측정 불가',complete:'측정 완료',partial:'일부 측정'}
 const letter=(id:string)=>id.split('_')[1].toUpperCase()
 const scores=ranking?.source==='model'?ranking.items.map(i=>i.score):[]
 const low=Math.min(...scores),span=Math.max(...scores)-low
 const level=(score:number)=>1+Math.round(4*(span>0?(score-low)/span:1))
 return <section ref={region} className="design-variants" aria-label="전략별 디자인 4종">
  <h3 className="variants-intro">마음에 드는 전략으로 디자인 4종 더 보기</h3>
  <p className="variants-intro">위의 기존 4전략 광고는 유지됩니다. 각 전략의 네 디자인은 같은 문구로 비교합니다.</p>
  <p role="status" className="variants-status">시안 상태: {state?.status||'pending'} · revision {state?.revision||0}{busy?' · 처리 중':''}</p>
  {stale&&<p role="alert">이전 입력의 시안입니다. 최신 결과로 다시 생성해 주세요.</p>}
  {error&&!editing&&<p role="alert">{error}</p>}{state?.error&&<p role="alert">{state.error.message}</p>}
  {state?.status==='failed'&&<p>{state.failed_templates?.length?`일부 시안 생성 실패: ${state.failed_templates.join(', ')}. 네 시안의 게시를 보류했습니다.`:'전체 시안을 생성하지 못했습니다.'} 입력 길이를 확인하고 다시 생성해 주세요. 기존 v2 광고는 유지됩니다.</p>}
  {state?.status==='completed'&&<>
   {state.ranking_status==='processing'&&<p role="status">모델 평가 중</p>}
   {state.ranking_error&&<p role="alert">{state.ranking_error.message}</p>}
   {state.ranking?.source==='mock'&&<p>시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다.</p>}
   {isTopDesignCloseCall(state,rankingDisabled)&&<p role="note">{closeCallMessage}</p>}
   <div className="carousel-wrap">
    <div className="carousel" ref={track} onScroll={sync}>{state.candidates.map((c,index)=>{const rank=ranking?.items.find(i=>i.candidate_id===c.candidate_id);const diagnostic=state.diagnostics.find(d=>d.candidate_id===c.candidate_id);const shot=urls[c.png.asset_id];return <article key={c.candidate_id} aria-label={`${c.template_id} 시안`} className={index===active?'active':undefined}>
     <div className="slide-shot">
      {rank&&<span className="rank-badge" aria-hidden="true">{rank.rank}위</span>}
      {shot?.url?<img src={shot.url} alt={`${strategyLabels[strategy]} ${c.template_id} 광고`} width="1080" height="1350"/>:<p role={shot?.error?'alert':'status'}>{shot?.error?'이미지를 조회하지 못했습니다.':'이미지 로딩 중'}</p>}
     </div>
     <div className="slide-info">
      <div className="slide-title"><h4>{letter(c.template_id)} · {names[c.design_name]||c.design_name}</h4>
       {rank&&ranking?.source==='model'&&<span className="meter" aria-hidden="true">{[1,2,3,4,5].map(n=><i key={n} className={n<=level(rank.score)?'on':undefined}/>)}</span>}</div>
      {rank&&<p className="slide-rank">{rank.rank}위 {ranking?.source==='model'?`· 상대 선호 score ${rank.score.toFixed(2)} · ${ranking.model_version}`:'· 시연용'}</p>}
      <p className="slide-headline">{c.copy?.headline}</p><p className="slide-price">가격: {c.facts?.price_text} · 편집 {c.edit_revision}회</p>
      {diagnostic&&<p className="chips" aria-hidden="true">{diagnostic.rules.map(r=><span key={r.rule_id} className={`chip ${r.status}`}>{ruleNames[r.rule_id]||r.rule_id} {statuses[r.status]||r.status}</span>)}</p>}
      <details><summary>가독성 진단 · {statuses[diagnostic?.coverage||'unavailable']}</summary><ul>{diagnostic?.rules.map(r=><li key={r.rule_id}>{ruleNames[r.rule_id]||r.rule_id}: {statuses[r.status]||r.status} · {r.explanation}</li>)}</ul><p>의도된 사진·장식 겹침도 경고를 유지합니다. 미측정 대비는 정상 판정하지 않습니다.</p></details>
      <div className="slide-actions">
       <button data-edit-id={c.candidate_id} disabled={!usable||!c.copy} onClick={()=>{setEditing(c.candidate_id);setValues({...c.copy!});setPrice(c.facts?.price_text||'');setError('')}}>시안 {letter(c.template_id)} 편집</button>
       <button className="secondary" disabled={!usable} onClick={()=>void download(c.candidate_id,'png')}>시안 PNG 다운로드</button>
       <button className="secondary" disabled={!usable} onClick={()=>void download(c.candidate_id,'pdf')}>시안 PDF 다운로드</button>
      </div>
     </div>
    </article>})}</div>
    <div className="carousel-arrows">
     <button type="button" aria-label="이전 시안 보기" disabled={active===0} onClick={()=>go(active-1)}>←</button>
     <button type="button" aria-label="다음 시안 보기" disabled={active>=state.candidates.length-1} onClick={()=>go(active+1)}>→</button>
    </div>
   </div>
   <div className="carousel-dots" aria-hidden="true">{state.candidates.map((c,index)=><span key={c.candidate_id} className={index===active?'on':undefined}/>)}</div>
   <div className="thumbs" role="group" aria-label="시안 바로 가기">{state.candidates.map((c,index)=>{const rank=ranking?.items.find(i=>i.candidate_id===c.candidate_id);const shot=urls[c.png.asset_id];return <button type="button" key={c.candidate_id} aria-pressed={index===active} aria-label={`${letter(c.template_id)}안 보기${rank?` (${rank.rank}위)`:''}`} onClick={()=>go(index)}>
    {shot?.url?<img src={shot.url} alt="" width="1080" height="1350"/>:<span className="thumb-empty"/>}
    <span>{rank?`${rank.rank}위 `:''}{letter(c.template_id)}</span>
   </button>})}</div>
   <p className="fine-print">같은 전략의 디자인에 대한 모델 성능은 별도 검증되지 않았습니다. 점수는 전환율·구매율·객관적 품질이 아니며 진단과 합산하지 않습니다. A~D 순서를 유지합니다.</p>
   <div className="save-actions">
    <button type="button" className="secondary" disabled={!usable} onClick={()=>{const c=state.candidates[active];if(c)void download(c.candidate_id,'png')}}>이 광고만 저장하기</button>
    <button type="button" disabled={!usable} onClick={()=>void downloadAll()}>광고 모두 저장하기</button>
   </div>
  </>}
  {editing&&(()=>{const c=state?.candidates.find(c=>c.candidate_id===editing);const shot=c&&urls[c.png.asset_id];const limits=[60,160,30];return <form aria-label="시안 고치기" className="design-edit" onSubmit={e=>{e.preventDefault();void run('edit')}}>
   <div className="design-edit-head">
    {shot?.url&&<img src={shot.url} alt="" width="1080" height="1350"/>}
    <div><h4>{c?`${letter(c.template_id)}안 · ${names[c.design_name]||c.design_name}`:'시안'} 고치기</h4>
     <p>고친 내용은 이 시안에만 들어가요. 처음 입력한 상품 정보와 다른 시안은 그대로예요.</p></div>
   </div>
   {(['headline','body','cta'] as const).map((f,i)=><div key={f} className="edit-field"><div className="edit-label"><label htmlFor={`${formId}-${f}`}>{['제목','본문','마무리 문구'][i]}</label><span className="edit-count" aria-hidden="true">{[...values[f]].length}/{limits[i]}</span></div>
    <textarea id={`${formId}-${f}`} autoFocus={i===0} required={f==='headline'} maxLength={limits[i]} aria-describedby={f==='cta'?`${formId}-cta-hint`:undefined} disabled={busy||stale||disabled} value={values[f]} onChange={e=>setValues(v=>({...v,[f]:e.target.value}))}/>
    {f==='cta'&&<p id={`${formId}-cta-hint`} className="edit-hint">손님이 할 행동을 짧게 적어요. 예: 지금 주문하세요</p>}</div>)}
   <div className="edit-field"><label htmlFor={`${formId}-price`}>가격</label>
    <input id={`${formId}-price`} required maxLength={40} aria-describedby={`${formId}-price-hint`} disabled={busy||stale||disabled} value={price} onChange={e=>setPrice(e.target.value)}/>
    <p id={`${formId}-price-hint`} className="edit-hint">가격을 바꾸면 본문이나 할인 문구에 남은 예전 가격도 같이 고쳐 주세요.</p></div>
   {error&&<p role="alert">{error}</p>}
   {busy&&<p role="status">시안을 다시 그리고 있어요. 몇 초 걸려요.</p>}
   <div className="edit-actions"><button disabled={busy||stale||disabled}>{busy?'적용하는 중…':'이 시안에 적용'}</button>
    <button type="button" className="secondary" disabled={busy} onClick={cancelEdit}>취소</button></div>
  </form>})()}
  <div className="variants-manage">
   <h4>다른 전략으로 만들기</h4>
   <div className="strategy-choices" role="group" aria-label="디자인 전략 선택">{(['emotional','price','visual','brand'] as Strategy[]).map(s=><button type="button" key={s} aria-pressed={strategy===s} disabled={disabled||Boolean(editing)} onClick={()=>select(s)}>{strategyLabels[s]} 전략 선택</button>)}</div>
   <p>선택 전략: <strong>{strategyLabels[strategy]}</strong></p>
   <details><summary>직접 확인한 행사 정보 입력 (선택)</summary><p>입력하지 않은 할인·행사·기간은 생성하지 않습니다. 완료된 시안의 행사 정보는 보존됩니다. 할인율은 입력한 소수 자릿수에서 반올림해 비교합니다.</p>{(['original_price','discount_text','promotion_text','period_text'] as const).map((f,i)=><label key={f}>{['할인 전 가격','할인율 (예: 30%)','행사명','행사 기간 (예: 2026.11.16–2026.11.20)'][i]}<input maxLength={f==='discount_text'?10:40} disabled={disabled||busy||state?.status==='completed'} value={promotion[f]} onChange={e=>setPromotion(v=>({...v,[f]:e.target.value}))}/></label>)}</details>
   <div className="manage-actions">
    <button disabled={disabled||busy||Boolean(editing)} onClick={()=>void run('create')}>이 전략으로 시안 4개 더 보기</button>
    <button className="secondary" disabled={disabled||busy||Boolean(editing)} onClick={()=>void run('get')}>시안 상태 다시 조회</button>
    {state?.status==='completed'&&<button className="secondary" disabled={!usable} onClick={()=>void run('rank')}>시안 ML 참고 순위 계산</button>}
    <button type="button" className="secondary back-to-v2" onClick={()=>region.current?.closest('.ad-rendering')?.scrollIntoView({block:'start',behavior:'smooth'})}>기존 4전략 광고로 돌아가기</button>
   </div>
   {state?.status==='completed'&&<p className="fine-print">v3 revision {state.revision} · {state.mock_copy?'Mock 카피':'기존 실제 카피 재사용'} · 추가 LLM 호출 없음</p>}
  </div>
 </section>
}
