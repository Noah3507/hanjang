import {test,expect,vi,afterEach} from 'vitest'
import {diagnostics} from './diagnostics'
import type {UploadHandle} from './uploads'
import type {RenderState} from './rendering'
const handle={token:'fake-test-token',upload:{job_id:'job'}} as UploadHandle
const pending={job_id:'job',operation:'diagnostics',status:'pending',is_current:false,revision:null,rules_version:'v1',results:[],warnings:[]}
afterEach(()=>vi.unstubAllGlobals())
test('sync POST pins revision and candidate asset pairs and uses auth',async()=>{
 const fetch=vi.fn<typeof globalThis.fetch>().mockResolvedValue(new Response(JSON.stringify(pending),{headers:{'Content-Type':'application/json'}}));vi.stubGlobal('fetch',fetch)
 const render={revision:3,candidates:[{candidate_id:'id',png:{asset_id:'asset'}}]} as RenderState
 await diagnostics(handle,render)
 const init=fetch.mock.calls[0][1]!
 expect(init.method).toBe('POST');expect(init.headers).toEqual({'X-Hanjang-Session':handle.token,'Content-Type':'application/json'})
 expect(JSON.parse(String(init.body))).toEqual({expected_render_revision:3,expected_candidates:[{candidate_id:'id',asset_id:'asset'}]})
})
test('malformed completed response is rejected, not silently normal',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({...pending,status:'completed',revision:1}))))
 await expect(diagnostics(handle)).rejects.toThrow('응답 형식')
})
test('error message and stale conflict are preserved',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({error:{message:'진단 중 광고 변경'}}),{status:409})))
 await expect(diagnostics(handle)).rejects.toThrow('진단 중 광고 변경')
})
