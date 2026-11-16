import {fireEvent,render,screen,waitFor} from '@testing-library/react'
import {beforeEach,expect,it,vi} from 'vitest'
import DesignVariants from './DesignVariants'
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
 fireEvent.change(screen.getByLabelText('v3 제목'),{target:{value:'저장하지 않을 제목'}})
 expect(screen.getByRole('button',{name:'감성 전략 선택'})).toBeDisabled()
 fireEvent.click(screen.getByRole('button',{name:'시안 편집 취소'}))
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
 fireEvent.click(await screen.findByRole('button',{name:'시안 ML 참고 순위 계산'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('모델을 사용할 수 없습니다.')
 expect(screen.getAllByRole('button',{name:'시안 PNG 다운로드'})[0]).toBeEnabled()
 expect(screen.queryByText(/상대 선호 score/)).not.toBeInTheDocument()
})
