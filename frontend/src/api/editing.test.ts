import {test,vi,expect,afterEach} from 'vitest'
import {editing,downloadAd} from './editing'
import type {UploadHandle} from './uploads'
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
