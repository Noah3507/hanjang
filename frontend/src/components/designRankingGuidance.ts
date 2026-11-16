import type {DesignState} from '../api/designs'

export const closeCallMessage='상위 시안들의 추천 점수가 비슷합니다. 작은 점수 차이만으로 디자인의 우열을 판단하기 어려우므로 직접 비교해 선택해 주세요.'

export function currentDesignRanking(state:DesignState|null,disabled:boolean){
 const ranking=state?.ranking
 if(!state||disabled||!state.is_current||state.editing||state.status!=='completed'||state.ranking_status!=='completed'||state.ranking_error
   ||!ranking||ranking.revision!==state.revision||state.candidates.length!==4||!Array.isArray(ranking.items)||ranking.items.length!==4)return null
 const ids=new Set(state.candidates.map(c=>c.candidate_id))
 if(ids.size!==4||state.candidates.some(c=>c.revision!==state.revision||c.png.revision!==state.revision)
   ||new Set(ranking.items.map(i=>i.candidate_id)).size!==4||ranking.items.some(i=>!ids.has(i.candidate_id)||!Number.isFinite(i.score)))return null
 const ordered=[...ranking.items].sort((a,b)=>a.rank-b.rank)
 if(ordered.some((i,n)=>i.rank!==n+1||(n>0&&i.score>ordered[n-1].score)))return null
 return ranking
}

export function isTopDesignCloseCall(state:DesignState|null,disabled=false){
 const ranking=currentDesignRanking(state,disabled),gap=state?.ranking_close_call_score_gap
 if(ranking?.source!=='model'||typeof gap!=='number'||!Number.isFinite(gap)||gap<=0)return false
 const ordered=[...ranking.items].sort((a,b)=>a.rank-b.rank)
 return ordered[0].score-ordered[1].score<=gap
}
