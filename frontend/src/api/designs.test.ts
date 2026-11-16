import {afterEach,expect,it,vi} from 'vitest'
import {getDesigns,createDesigns} from './designs'
import type {UploadHandle} from './uploads'
import type {RenderState} from './rendering'
const handle={token:'synthetic-test-token',upload:{job_id:'job'}} as UploadHandle
function body(){return {operation:'designs_v3',strategy:'price',status:'completed',revision:2,is_current:true,mock_copy:true,snapshot:'a'.repeat(64),candidates:'abcd'.split('').map((c,i)=>({candidate_id:c,template_id:'price_'+c,strategy:'price',revision:2,png:{asset_id:String(i).repeat(32),revision:2,width:1080,height:1350}}))}}
afterEach(()=>vi.unstubAllGlobals())
it('accepts four same-strategy templates and sends session-bound source snapshot',async()=>{
 const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>body()});vi.stubGlobal('fetch',fetch)
 const r=await createDesigns(handle,'price',{revision:1,source_asset_id:'1'.repeat(32),copy_key:'2'.repeat(32)} as RenderState)
 expect(r.candidates).toHaveLength(4)
 expect(fetch.mock.calls[0][1].headers['X-Hanjang-Session']).toBe('synthetic-test-token')
 expect(JSON.parse(fetch.mock.calls[0][1].body).expected_render_revision).toBe(1)
})
it('rejects duplicate IDs or a result for a different strategy',async()=>{
 const b=body();b.candidates[1].candidate_id='a';vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>b}))
 await expect(getDesigns(handle,'price')).rejects.toThrow('응답')
 b.strategy='brand';await expect(getDesigns(handle,'price')).rejects.toThrow('응답')
})
