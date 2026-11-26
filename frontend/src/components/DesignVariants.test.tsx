import {fireEvent,render,screen,waitFor} from '@testing-library/react'
import {beforeEach,expect,it,vi} from 'vitest'
import DesignVariants from './DesignVariants'
import {isTopDesignCloseCall,closeCallMessage} from './designRankingGuidance'
import * as api from '../api/designs'
import type {DesignState,Strategy} from '../api/designs'
import type {RenderState} from '../api/rendering'
import type {UploadHandle} from '../api/uploads'
vi.mock('../api/designs',()=>({getDesigns:vi.fn(),createDesigns:vi.fn(),rankDesigns:vi.fn(),editDesign:vi.fn(),downloadDesign:vi.fn()}))
vi.mock('../api/rendering',()=>({preview:vi.fn().mockResolvedValue(new Blob(['image']))}))
const handle={token:'synthetic-only',upload:{job_id:'test-job'}} as UploadHandle
const source={revision:1,source_asset_id:'1'.repeat(32),copy_key:'2'.repeat(32)} as RenderState
function state(strategy:Strategy,status:DesignState['status']='pending'):DesignState{return {operation:'designs_v3',strategy,status,revision:status==='completed'?1:0,source_revision:1,
 source_asset_id:'1'.repeat(32),copy_key:'2'.repeat(32),template_version:'test',is_current:true,editing:false,snapshot:'a'.repeat(64),mock_copy:true,
 candidates:status==='completed'?'abcd'.split('').map((c,i)=>({candidate_id:strategy+c,strategy,revision:1,template_id:strategy+'_'+c,design_name:c,generation_revision:1,edit_revision:0,original_price_text:'10원',
 copy:{headline:'제목 '+c,body:'본문',cta:'보기'},png:{asset_id:String(i).repeat(32),url:'/private',revision:1,width:1080,height:1350},facts:{store_name:'상점',product_name:'상품',price_text:'10원',address:null,instagram_handle:null}})):[],
 diagnostics:[],ranking:null,ranking_status:'pending',ranking_error:null,error:null}}
beforeEach(()=>{vi.clearAllMocks();sessionStorage.clear();vi.mocked(api.getDesigns).mockImplementation(async(_h,s)=>state(s));vi.stubGlobal('URL',Object.assign(URL,{createObjectURL:vi.fn(()=> 'blob:test'),revokeObjectURL:vi.fn()}))})

it('creates four same-strategy designs and cancelling edit preserves the copy',async()=>{
 vi.mocked(api.createDesigns).mockResolvedValue(state('price','completed'))
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 await waitFor(()=>expect(screen.getByRole('button',{name:'이 전략으로 시안 4개 더 보기'})).toBeEnabled())
 fireEvent.click(screen.getByRole('button',{name:'이 전략으로 시안 4개 더 보기'}))
 expect(await screen.findAllByRole('article')).toHaveLength(4)
 fireEvent.click(screen.getByRole('button',{name:'시안 A 편집'}))
 fireEvent.change(screen.getByLabelText('제목'),{target:{value:'저장하지 않을 제목'}})
 expect(screen.getByRole('button',{name:'감성 전략 선택'})).toBeDisabled()
 fireEvent.click(screen.getByRole('button',{name:'취소'}))
 expect(api.editDesign).not.toHaveBeenCalled()
 expect(screen.queryByText('저장하지 않을 제목')).not.toBeInTheDocument()
})

it('late response for price cannot replace the newly selected brand strategy',async()=>{
 let resolve:(s:DesignState)=>void=()=>{}
 vi.mocked(api.getDesigns).mockImplementation(async(_h,s)=>s==='price'?new Promise<DesignState>(r=>{resolve=r}):state(s,'completed'))
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 fireEvent.click(screen.getByRole('button',{name:'브랜드 전략 선택'}))
 expect(await screen.findByRole('article',{name:'brand_a 시안'})).toBeInTheDocument()
 resolve(state('price','completed'))
 await waitFor(()=>expect(screen.queryByRole('article',{name:'price_a 시안'})).not.toBeInTheDocument())
})

it('model failure keeps designs available and never displays fake model scores',async()=>{
 vi.mocked(api.getDesigns).mockResolvedValue(state('price','completed'))
 vi.mocked(api.rankDesigns).mockResolvedValue({...state('price','completed'),ranking_status:'failed',ranking_error:{code:'RANKING_MODEL_UNAVAILABLE',message:'모델을 사용할 수 없습니다.'}})
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 fireEvent.click(await screen.findByRole('button',{name:'추천 순위 다시 계산'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('모델을 사용할 수 없습니다.')
 expect(screen.getAllByRole('button',{name:'시안 PNG 다운로드'})[0]).toBeEnabled()
 expect(screen.queryByText(/추천 점수/)).not.toBeInTheDocument()
})

function ranked(strategy:Strategy='price',scores=[0.2,0,-1,-2]){
 const s=state(strategy,'completed');s.ranking_status='completed';s.ranking_close_call_score_gap=0.2
 s.ranking={source:'model',model_version:'bt-logistic-v1',revision:1,items:s.candidates.map((c,i)=>({candidate_id:c.candidate_id,rank:i+1,score:scores[i]}))}
 return s
}

it('uses raw scores, inclusive manifest boundary, top two only, and no fallback threshold',()=>{
 expect(isTopDesignCloseCall(ranked())).toBe(true)
 expect(isTopDesignCloseCall(ranked('price',[1,0,-0.01,-0.02]))).toBe(false)
 expect(isTopDesignCloseCall(ranked('price',[0.2001,0,-1,-2]))).toBe(false)
 expect(isTopDesignCloseCall(ranked('price',[0.1999,0,-1,-2]))).toBe(true)
 const s=ranked();s.ranking_close_call_score_gap=0.1;expect(isTopDesignCloseCall(s)).toBe(false)
 s.ranking_close_call_score_gap=null;expect(isTopDesignCloseCall(s)).toBe(false)
})

it('never judges failed, missing, nonfinite, mismatched or stale results',()=>{
 const cases=[{is_current:false},{editing:true},{ranking_status:'failed'},{ranking_error:{code:'failed',message:'failed'}},{ranking:null},{revision:2}]
 for(const override of cases)expect(isTopDesignCloseCall({...ranked(),...override})).toBe(false)
 const s=ranked();s.ranking!.items[0].score=NaN;expect(isTopDesignCloseCall(s)).toBe(false)
 s.ranking!.items[0].score=undefined as unknown as number;expect(isTopDesignCloseCall(s)).toBe(false)
 s.ranking!.items.pop();expect(isTopDesignCloseCall(s)).toBe(false)
 expect(isTopDesignCloseCall(ranked(),true)).toBe(false)
 const mock=ranked();mock.ranking!.source='mock';expect(isTopDesignCloseCall(mock)).toBe(false)
})

it.each(['emotional','price','visual','brand'] as Strategy[])('shows guidance and two-decimal model scores for %s',async strategy=>{
 vi.mocked(api.getDesigns).mockResolvedValue(ranked(strategy))
 render(<DesignVariants handle={handle} render={source} disabled={false} selectedStrategy={strategy}/> )
 expect(await screen.findByRole('note')).toHaveTextContent(closeCallMessage)
 expect(screen.getByText(/추천 점수 0.20/)).toBeInTheDocument()
 expect(screen.getAllByRole('article')).toHaveLength(4)
})

it('hides rounded near scores and stale scores after source revision changes',async()=>{
 vi.mocked(api.getDesigns).mockResolvedValue(ranked('price',[0.2001,0,-1,-2]))
 const {rerender}=render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 expect(await screen.findByText(/추천 점수 0.20/)).toBeInTheDocument()
 expect(screen.queryByRole('note')).not.toBeInTheDocument()
 vi.mocked(api.getDesigns).mockResolvedValue({...ranked(),is_current:false})
 rerender(<DesignVariants handle={handle} render={{...source,revision:2}} disabled={false}/> )
 expect(await screen.findByText('이전 입력의 시안입니다. 최신 결과로 다시 생성해 주세요.')).toBeInTheDocument()
 expect(screen.queryByRole('note')).not.toBeInTheDocument()
 expect(screen.queryByText(/추천 점수/)).not.toBeInTheDocument()
})

it('shows the designs as a carousel in A to D order with one image request per design',async()=>{
 const {preview}=await import('../api/rendering')
 const mixed=ranked('price');mixed.ranking!.items=mixed.candidates.map((c,i)=>({candidate_id:c.candidate_id,rank:[3,1,4,2][i],score:[0.1,0.9,-0.4,0.3][i]}))
 vi.mocked(api.getDesigns).mockResolvedValue(mixed)
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 await waitFor(()=>expect(screen.getAllByRole('img',{name:/price_[a-d] 광고/})).toHaveLength(4))
 expect(preview).toHaveBeenCalledTimes(4)
 expect(screen.getAllByRole('article').map(a=>a.getAttribute('aria-label'))).toEqual(['price_a 시안','price_b 시안','price_c 시안','price_d 시안'])
 const thumbs=screen.getByRole('group',{name:'시안 바로 가기'})
 expect(Array.from(thumbs.querySelectorAll('button')).map(b=>b.getAttribute('aria-label'))).toEqual(['A안 보기 (3위)','B안 보기 (1위)','C안 보기 (4위)','D안 보기 (2위)'])
 expect(screen.getByRole('button',{name:'이전 시안 보기'})).toBeDisabled()
 fireEvent.click(screen.getByRole('button',{name:'B안 보기 (1위)'}))
 expect(screen.getByRole('button',{name:'B안 보기 (1위)'})).toHaveAttribute('aria-pressed','true')
 expect(screen.getByRole('article',{name:'price_b 시안'})).toHaveClass('active')
 fireEvent.click(screen.getByRole('button',{name:'다음 시안 보기'}))
 expect(screen.getByRole('article',{name:'price_c 시안'})).toHaveClass('active')
})

it('saves the shown design or all four as PNG',async()=>{
 vi.mocked(api.getDesigns).mockResolvedValue(state('price','completed'))
 vi.mocked(api.downloadDesign).mockResolvedValue(new Blob(['png']))
 const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 fireEvent.click(await screen.findByRole('button',{name:'D안 보기'}))
 fireEvent.click(screen.getByRole('button',{name:'이 광고만 저장하기'}))
 await waitFor(()=>expect(api.downloadDesign).toHaveBeenCalledTimes(1))
 expect(vi.mocked(api.downloadDesign).mock.calls[0][3].template_id).toBe('price_d')
 await waitFor(()=>expect(screen.getByRole('button',{name:'광고 모두 저장하기'})).toBeEnabled())
 fireEvent.click(screen.getByRole('button',{name:'광고 모두 저장하기'}))
 await waitFor(()=>expect(api.downloadDesign).toHaveBeenCalledTimes(5))
 expect(vi.mocked(api.downloadDesign).mock.calls.slice(1).map(c=>[c[3].template_id,c[4]])).toEqual([['price_a','png'],['price_b','png'],['price_c','png'],['price_d','png']])
 click.mockRestore()
})

it('edit form names the design in plain words and keeps the four designs on screen while redrawing',async()=>{
 const done=state('price','completed')
 const edited={...done,revision:2,candidates:done.candidates.map(c=>c.template_id==='price_b'?{...c,edit_revision:1,facts:{...c.facts!,price_text:'9원'}}:c)}
 vi.mocked(api.getDesigns).mockResolvedValueOnce(done).mockResolvedValue(edited)
 vi.mocked(api.editDesign).mockResolvedValue({...done,status:'processing'})
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 fireEvent.click(await screen.findByRole('button',{name:'시안 B 편집'}))
 const form=screen.getByRole('form',{name:'시안 고치기'})
 expect(form).toHaveTextContent('B안 · b 고치기')
 expect(form).not.toHaveTextContent(/v2|v3|CTA/)
 expect(screen.getByLabelText('마무리 문구')).toHaveValue('보기')
 fireEvent.change(screen.getByLabelText('가격'),{target:{value:'9원'}})
 fireEvent.click(screen.getByRole('button',{name:'이 시안에 적용'}))
 expect(await screen.findByText('시안을 다시 그리고 있어요. 몇 초 걸려요.')).toBeInTheDocument()
 expect(screen.getAllByRole('article')).toHaveLength(4)
 await waitFor(()=>expect(screen.queryByRole('form',{name:'시안 고치기'})).not.toBeInTheDocument(),{timeout:3000})
 expect(screen.getAllByRole('article')[1]).toHaveTextContent('가격 9원 · 1번 고침')
 expect(screen.getAllByRole('article')[0]).toHaveTextContent('가격 10원')
 expect(screen.getAllByRole('article')[0]).not.toHaveTextContent('고침')
 await waitFor(()=>expect(screen.getByRole('button',{name:'시안 B 편집'})).toHaveFocus())
})

it('an edit the server refuses is explained inside the form',async()=>{
 vi.mocked(api.getDesigns).mockResolvedValue(state('price','completed'))
 vi.mocked(api.editDesign).mockRejectedValue(new Error('문구에 남은 이전 가격도 직접 수정해 주세요.'))
 render(<DesignVariants handle={handle} render={source} disabled={false}/> )
 fireEvent.click(await screen.findByRole('button',{name:'시안 A 편집'}))
 fireEvent.click(screen.getByRole('button',{name:'이 시안에 적용'}))
 const form=screen.getByRole('form',{name:'시안 고치기'})
 await waitFor(()=>expect(form.querySelector('[role=alert]')).toHaveTextContent('이전 가격도 직접 수정'))
 expect(screen.getAllByRole('alert')).toHaveLength(1)
})
