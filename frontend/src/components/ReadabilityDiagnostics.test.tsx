import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {vi,test,expect,beforeEach} from 'vitest'
import ReadabilityDiagnostics from './ReadabilityDiagnostics'
import {diagnostics,type DiagnosticsState} from '../api/diagnostics'
import type {UploadHandle} from '../api/uploads'
import type {RenderState} from '../api/rendering'
vi.mock('../api/diagnostics',()=>({diagnostics:vi.fn()}))
const handle={token:'synthetic',upload:{job_id:'job'}} as UploadHandle
const source={revision:1,copy_key:'copy',source_asset_id:'source',candidates:['emotional','price','visual','brand'].map(strategy=>({candidate_id:strategy,strategy,png:{asset_id:strategy}}))} as RenderState
export const pending={job_id:'job',operation:'diagnostics',status:'pending',revision:null,is_current:false,rules_version:'v1',results:[],warnings:[],error:null} as DiagnosticsState
export const completed={...pending,status:'completed',revision:1,is_current:true,results:source.candidates.map(c=>({candidate_id:c.candidate_id,strategy:c.strategy,asset_id:c.png.asset_id,coverage:'partial',rules:['contrast','font_size','layout','density'].map((rule_id,i)=>({rule_id,status:['normal','caution','problem','unavailable'][i],coverage:i===3?'unavailable':'complete',measured_value:i===0?{minimum:8}:i===1?{minimum:32}:null,unit:'px',criterion:'검증 기준',explanation:'실제 근거',action:'미리보기를 확인해 주세요.'}))}))} as DiagnosticsState
beforeEach(()=>{vi.resetAllMocks();vi.mocked(diagnostics).mockResolvedValue(pending)})
test('no result differs from normal and four candidates expose all statuses',async()=>{
 render(<ReadabilityDiagnostics handle={handle} render={source} disabled={false}/>)
 expect(await screen.findByText(/아직 진단 결과가 없습니다/)).toBeInTheDocument()
 vi.mocked(diagnostics).mockResolvedValue(completed)
 fireEvent.click(screen.getByRole('button',{name:'가독성 진단 실행'}))
 expect(await screen.findAllByRole('article')).toHaveLength(4)
 expect(screen.getAllByText('글자 크기 · 주의')).toHaveLength(4)
 expect(screen.getAllByText('경계·겹침 · 문제')).toHaveLength(4)
 expect(screen.getAllByText('텍스트 블록 밀도 · 측정 불가')).toHaveLength(4)
 expect(screen.getAllByText(/확인된 최소 글자 32/)).toHaveLength(4)
 expect(diagnostics).toHaveBeenLastCalledWith(handle,source)
})
test('failure and manual retry are safe',async()=>{
 render(<ReadabilityDiagnostics handle={handle} render={source} disabled={false}/>)
 await screen.findByText(/아직 진단 결과가 없습니다/)
 vi.mocked(diagnostics).mockRejectedValueOnce(Error('다시 시도해 주세요.'))
 fireEvent.click(screen.getByRole('button',{name:'가독성 진단 실행'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('다시 시도')
 vi.mocked(diagnostics).mockResolvedValue(completed);fireEvent.click(screen.getByRole('button',{name:'가독성 진단 실행'}))
 expect(await screen.findAllByRole('article')).toHaveLength(4)
})
test('stale revision and mismatched asset cannot be shown as current',async()=>{
 vi.mocked(diagnostics).mockResolvedValue(completed)
 render(<ReadabilityDiagnostics handle={handle} render={{...source,revision:2}} disabled={false}/>)
 expect(await screen.findByRole('alert')).toHaveTextContent('이전 revision')
 expect(screen.queryAllByRole('article')).toHaveLength(0)
})
test('old response after edit cannot overwrite new state and duplicate click blocked',async()=>{
 const view=render(<ReadabilityDiagnostics handle={handle} render={source} disabled={false}/>)
 await screen.findByText(/아직 진단 결과가 없습니다/)
 let resolve!:(v:DiagnosticsState)=>void
 vi.mocked(diagnostics).mockReturnValueOnce(new Promise(r=>resolve=r))
 fireEvent.click(screen.getByRole('button',{name:'가독성 진단 실행'}))
 expect(screen.getByRole('button',{name:'가독성 진단 실행'})).toBeDisabled()
 view.rerender(<ReadabilityDiagnostics handle={handle} render={{...source,revision:2}} disabled={false}/>)
 resolve(completed)
 await waitFor(()=>expect(screen.getByText(/아직 진단 결과가 없습니다/)).toBeInTheDocument())
 expect(screen.queryAllByRole('article')).toHaveLength(0)
})
test('refresh can observe processing then retrieve completed state',async()=>{
 vi.mocked(diagnostics).mockResolvedValueOnce({...pending,status:'processing',revision:1,is_current:true}).mockResolvedValue(completed)
 render(<ReadabilityDiagnostics handle={handle} render={source} disabled={false}/>)
 expect(await screen.findByText('가독성 진단 요청 처리 중')).toBeInTheDocument()
 await waitFor(()=>expect(screen.getAllByRole('article')).toHaveLength(4),{timeout:2500})
})
test('failed asset revalidation hides previously normal cards',async()=>{
 vi.mocked(diagnostics).mockResolvedValue(completed)
 render(<ReadabilityDiagnostics handle={handle} render={source} disabled={false}/>)
 expect(await screen.findAllByRole('article')).toHaveLength(4)
 vi.mocked(diagnostics).mockRejectedValueOnce(Error('광고 파일이 변경됐습니다.'))
 fireEvent.click(screen.getByRole('button',{name:'진단 다시 조회'}))
 expect(await screen.findByRole('alert')).toHaveTextContent('광고 파일이 변경')
 expect(screen.queryAllByRole('article')).toHaveLength(0)
})
