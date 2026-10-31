import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {vi,test,expect,beforeEach} from 'vitest'
import AdEditor from './AdEditor'
import {editing,downloadAd,type EditState} from '../api/editing'
import type {Draft,UploadHandle} from '../api/uploads'
import type {RenderState} from '../api/rendering'
vi.mock('../api/editing',()=>({editing:vi.fn(),downloadAd:vi.fn()}))
const handle={token:'test-only',upload:{job_id:'job'}} as UploadHandle
const draft={facts:{store_name:'가게',product_name:'상품',price_text:' 3,000 원 ',address:null,instagram_handle:null},mood:'warm'} as Draft
const state={revision:2,status:'completed',source_asset_id:'source',copy_key:'key',is_current:true,candidates:[{candidate_id:'a',strategy:'emotional',copy:{headline:'현재 편집된 제목',body:'',cta:''},revision:2,png:{asset_id:'asset'}}]} as RenderState
const pending={operation:'editing',status:'pending',is_current:false} as EditState
const complete={operation:'editing',status:'completed',is_current:true,edit_id:'edit',target_revision:3,base_revision:2,candidate_id:'a'} as EditState
beforeEach(()=>{vi.resetAllMocks();vi.mocked(editing).mockResolvedValue(pending);URL.createObjectURL=vi.fn(()=> 'blob:local');URL.revokeObjectURL=vi.fn()})
function setup(extra={}){const applied=vi.fn(),busy=vi.fn();return {...render(<AdEditor handle={handle} draft={draft} render={state} disabled={false} onApplied={applied} onBusy={busy} {...extra}/>),applied,busy}}
test('latest successful copy, unchanged apply disabled, cancel preserves original and focus',async()=>{
 setup();await waitFor(()=>expect(editing).toHaveBeenCalled())
 fireEvent.click(screen.getByRole('button',{name:'문구 편집'}))
 expect(screen.getByLabelText('제목')).toHaveValue('현재 편집된 제목')
 expect(screen.getByRole('button',{name:'적용하고 재렌더링'})).toBeDisabled()
 fireEvent.change(screen.getByLabelText('제목'),{target:{value:'새 문구'}})
 fireEvent.click(screen.getByRole('button',{name:'편집 취소'}))
 expect(screen.queryByRole('form')).not.toBeInTheDocument()
 await waitFor(()=>expect(screen.getByRole('button',{name:'문구 편집'})).toHaveFocus())
 expect(editing).toHaveBeenCalledTimes(1)
})
test('apply exact current revision then reload success',async()=>{
 const {applied}=setup();await waitFor(()=>expect(editing).toHaveBeenCalledTimes(1))
 fireEvent.click(screen.getByRole('button',{name:'문구 편집'}));fireEvent.change(screen.getByLabelText('제목'),{target:{value:'새 문구'}})
 vi.mocked(editing).mockResolvedValue(complete)
 fireEvent.click(screen.getByRole('button',{name:'적용하고 재렌더링'}))
 await waitFor(()=>expect(applied).toHaveBeenCalledTimes(1))
 expect(editing).toHaveBeenLastCalledWith(handle,{candidate:'a',copy:{headline:'새 문구',body:'',cta:''},draft,render:state})
})
test('API error leaves edited values and last successful copy visible',async()=>{
 setup();await waitFor(()=>expect(editing).toHaveBeenCalled())
 fireEvent.click(screen.getByRole('button',{name:'문구 편집'}));fireEvent.change(screen.getByLabelText('제목'),{target:{value:'새 문구'}})
 vi.mocked(editing).mockRejectedValue(Error('충돌: 다시 조회'))
 fireEvent.click(screen.getByRole('button',{name:'적용하고 재렌더링'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('충돌')
 expect(screen.getByLabelText('제목')).toHaveValue('새 문구')
 expect(screen.getByText(/현재 성공본/)).toHaveTextContent('현재 편집된 제목')
})
test('late completion cannot replace changed input',async()=>{
 const {rerender,applied,busy}=setup();await waitFor(()=>expect(editing).toHaveBeenCalledTimes(1))
 fireEvent.click(screen.getByRole('button',{name:'문구 편집'}));fireEvent.change(screen.getByLabelText('제목'),{target:{value:'새 문구'}})
 let resolve!:(v:EditState)=>void;vi.mocked(editing).mockReturnValue(new Promise(r=>resolve=r))
 fireEvent.click(screen.getByRole('button',{name:'적용하고 재렌더링'}))
 rerender(<AdEditor handle={handle} draft={draft} render={state} disabled={true} onApplied={applied} onBusy={busy}/>)
 resolve(complete);await waitFor(()=>expect(screen.getByRole('button',{name:'문구 편집'})).toBeDisabled())
 expect(applied).not.toHaveBeenCalled()
})
test('download errors and stale snapshot disable export',async()=>{
 const {rerender,applied,busy}=setup();vi.mocked(downloadAd).mockRejectedValue(Error('만료된 광고'))
 fireEvent.click(screen.getByRole('button',{name:'A4 PDF 다운로드'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('만료')
 rerender(<AdEditor handle={handle} draft={draft} render={state} disabled={true} onApplied={applied} onBusy={busy}/>)
 expect(screen.getByRole('button',{name:'PNG 다운로드'})).toBeDisabled()
})
