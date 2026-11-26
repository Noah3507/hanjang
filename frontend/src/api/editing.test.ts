import {test,vi,expect,afterEach} from 'vitest'
import {editing,downloadAd} from './editing'
import type {Draft,UploadHandle} from './uploads'
import type {RenderState} from './rendering'
const handle={token:'synthetic-test-token',upload:{job_id:'job'}} as UploadHandle
afterEach(()=>vi.unstubAllGlobals())
test('auth binary download uses pinned revision and rejects incorrect MIME',async()=>{
 const fetch=vi.fn<typeof globalThis.fetch>().mockResolvedValue(new Response(new Blob(['png']),{headers:{'Content-Type':'image/png'}}));vi.stubGlobal('fetch',fetch)
 await downloadAd(handle,'candidate',4,'png')
 expect(fetch.mock.calls[0][0]).toContain('expected_revision=4')
 expect(fetch.mock.calls[0][1]).toEqual({headers:{'X-Hanjang-Session':handle.token}})
 await expect(downloadAd(handle,'candidate',4,'pdf')).rejects.toThrow('형식')
})
test('editing rejects malformed envelopes',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({operation:'editing',status:'completed',is_current:true}),{headers:{'Content-Type':'application/json'}})))
 await expect(editing(handle)).rejects.toThrow('형식')
})
test('edit request carries the saved ad goal and photo mode',async()=>{
 const fetch=vi.fn<typeof globalThis.fetch>().mockResolvedValue(Response.json({operation:'editing',status:'pending',edit_id:null,candidate_id:null,base_revision:null,target_revision:null,is_current:true,error:null}));vi.stubGlobal('fetch',fetch)
 const draft={job_id:'job',status:'pending',facts:{store_name:'가게',product_name:'상품',price_text:'10,000원',address:null,instagram_handle:null},mood:'warm',expires_at:'',ad_goal:'store_visit',photo_mode:'original'} as Draft
 const render={revision:2,candidates:[{candidate_id:'c1'}],source_asset_id:'asset',copy_key:'key'} as RenderState
 await editing(handle,{candidate:'c1',copy:{headline:'제목',body:'본문',cta:'방문'},draft,render})
 expect(JSON.parse(String(fetch.mock.calls[0][1]!.body)).expected_input).toMatchObject({ad_goal:'store_visit',photo_mode:'original'})
})
