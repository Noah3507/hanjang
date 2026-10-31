"""Fake executor for API/state tests; opt-in real Chromium tests are separate."""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import os
from pathlib import Path
import re
import zlib
import pytest
from PIL import Image
from test_rendering import service, fake_render, draft, png
from app.services.render_execution import RenderExecution, RenderFailure
from app.services.uploads import now

def prepared(service):
    app,c,h,m,b,body,raw=service
    assert c.post(b+'/rendering',headers=h,json=body).status_code==202
    render=c.get(b+'/rendering',headers=h).json()
    return render,{**body,'expected_revision':render['revision'],'expected_candidate_ids':[x['candidate_id'] for x in render['candidates']],
        'copy':{'headline':'잠깐의 여유','body':'한 잔과 함께 쉬어가세요.','cta':'만나보세요'}}

def target(base,render):return base+'/candidates/'+render['candidates'][0]['candidate_id']

def test_edit_identity_revisions_reuse_download_and_original(service):
    app,c,h,m,b,body,raw=service;r,edit=prepared(service)
    old=[c.get(x['png']['url'],headers=h).content for x in r['candidates']]
    c.post(b+'/ranking',headers=h,json={'expected_render_revision':r['revision'],'expected_candidate_ids':edit['expected_candidate_ids']})
    assert c.patch(target(b,r),headers=h,json=edit).status_code==202
    status=c.get(b+'/editing',headers=h).json();assert status['status']=='completed'
    updated=c.get(b+'/rendering',headers=h).json()
    assert updated['revision']==2 and updated['copy_key']==r['copy_key']
    assert [x['candidate_id'] for x in updated['candidates']]==edit['expected_candidate_ids']
    assert all(x['revision']==x['png']['revision']==2 for x in updated['candidates'])
    assert updated['candidates'][0]['copy']==edit['copy']
    assert [x['png']['asset_id'] for x in updated['candidates'][1:]]==[x['png']['asset_id'] for x in r['candidates'][1:]]
    assert [c.get(x['png']['url'],headers=h).content for x in updated['candidates'][1:]]==old[1:]
    assert not c.get(b+'/ranking',headers=h).json()['is_current']
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==raw
    assert c.get(b+'/copy-generation',headers=h).json()['variants'][0]['copy']!=edit['copy']
    assert c.post(b+'/rendering',headers=h,json=body).json()['revision']==2
    assert c.patch(target(b,r),headers=h,json=edit).json()['edit_id']==status['edit_id']
    second={**edit,'expected_revision':2,'copy':{**edit['copy'],'headline':'다시 만나는 한 잔'}}
    c.patch(target(b,r),headers=h,json=second)
    latest=c.get(b+'/rendering',headers=h).json();assert latest['revision']==3
    assert latest['candidates'][0]['copy']==second['copy']
    assert c.patch(target(b,r),headers=h,json=edit).status_code==409
    url=target(b,r)+'/download?format=png&expected_revision='
    assert c.get(url+'2',headers=h).status_code==409
    downloaded=c.get(url+'3',headers=h)
    assert downloaded.content==c.get(latest['candidates'][0]['png']['url'],headers=h).content
    assert 'attachment' in downloaded.headers['content-disposition'] and 'filename*=UTF-8' in downloaded.headers['content-disposition']
    assert downloaded.headers['cache-control']=='no-store'
    from jsonschema import validate
    import json
    validate({'candidates':latest['candidates']},json.loads(Path('tests/fixtures/contracts/candidates.schema.json').read_text()))

@pytest.mark.parametrize('field,value',[('headline',''),('headline','가'*61),('body','가'*161),('cta','가'*31),('headline','<script>'),('headline','🙂'),('headline','가\u200d나'),('headline','가\ufe0f')])
def test_invalid_copy(service,field,value):
    _,c,h,_,b,_,_=service;r,edit=prepared(service);edit['copy'][field]=value
    assert c.patch(target(b,r),headers=h,json=edit).status_code==422
    assert c.get(b+'/rendering',headers=h).json()==r

@pytest.mark.parametrize('field',['expected_revision','expected_asset_id','expected_input','expected_copy_key','expected_candidate_ids'])
def test_stale_request(service,field):
    _,c,h,_,b,_,_=service;r,edit=prepared(service)
    if field=='expected_revision':edit[field]=99
    elif field=='expected_input':edit[field]={**edit[field],'product_features':'다름'}
    elif field=='expected_candidate_ids':edit[field]=['0'*32,*edit[field][1:]]
    else:edit[field]='0'*32
    assert c.patch(target(b,r),headers=h,json=edit).status_code==409

def test_failure_preserves_success_and_retry(service):
    app,c,h,_,b,_,_=service;r,edit=prepared(service)
    app.state.render_store.executor=lambda *args: (_ for _ in ()).throw(RenderFailure('RENDER_LAYOUT_OVERFLOW'))
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/editing',headers=h).json()['status']=='failed'
    assert c.get(b+'/rendering',headers=h).json()==r
    app.state.render_store.executor=fake_render
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/editing',headers=h).json()['status']=='completed'
    assert c.get(b+'/rendering',headers=h).json()['revision']>r['revision']

def test_change_during_edit_does_not_publish(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service)
    def changed(d,copy,data):
        owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
        app.state.upload_store.save_draft(owner,m['job_id'],d.model_copy(update={'product_features':'changed'}))
        return fake_render(d,copy,data)
    app.state.render_store.executor=changed
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/editing',headers=h).json()['status']=='failed'
    latest=c.get(b+'/rendering',headers=h).json()
    assert latest['revision']==r['revision'] and not latest['is_current']

def test_noop_auth_ttl_and_limits(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service);edit['copy']=r['candidates'][0]['copy']
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/rendering',headers=h).json()['revision']==r['revision']
    url=target(b,r)+'/download?format=png&expected_revision=1'
    assert c.get(url).status_code==401
    other={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
    assert c.get(url,headers=other).status_code==404
    assert c.get(b+'/editing',headers=other).status_code==404
    assert c.patch(target(b,r),headers=other,json=edit).status_code==404
    assert c.patch(target(b,r),headers=h,content=b'x'*17000).status_code==413
    assert c.get(url.replace('format=png','format=svg'),headers=h).status_code==422
    app.state.upload_store.records[m['job_id']].upload.expires_at=now()-timedelta(seconds=1)
    assert c.get(url,headers=h).status_code==410

def test_pending_duplicate_busy_and_last_success(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service)
    from app.schemas.editing import EditRequest
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);store=app.state.editor_store
    response,task=store.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit))
    assert response.status=='processing' and c.get(b+'/rendering',headers=h).json()==r
    assert store.start(owner,m['job_id'],r['candidates'][0]['candidate_id'],EditRequest.model_validate(edit))[1] is None
    other={**edit,'copy':{**edit['copy'],'headline':'다른 동시 요청'}}
    assert c.patch(target(b,r),headers=h,json=other).status_code==409
    store.finish(owner,m['job_id'],task)
    assert c.get(b+'/rendering',headers=h).json()['revision']==2

def test_pdf_failure_cache_and_revalidation(service):
    app,c,h,_,b,_,_=service;r,_=prepared(service);url=target(b,r)+'/download?format=pdf&expected_revision=1'
    app.state.export_service.pdf=lambda _:(_ for _ in ()).throw(Exception('internal path'))
    response=c.get(url,headers=h)
    assert response.status_code==503 and 'internal path' not in response.text
    from app.services.uploads import UploadError
    app.state.export_service.pdf=lambda _:(_ for _ in ()).throw(UploadError(503,'PDF_FAILED','PDF 생성 실패'))
    assert c.get(url,headers=h).status_code==503
    assert c.get(b+'/rendering',headers=h).json()==r
    count=[]
    def success(data):count.append(1);return b'%PDF-fake-test-only'
    app.state.export_service.pdf=success
    assert c.get(url,headers=h).content==b'%PDF-fake-test-only'
    assert c.get(url,headers=h).status_code==200 and len(count)==1

def test_changed_asset_is_not_downloaded_or_edited(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service)
    asset=r['candidates'][0]['png']['asset_id'];app.state.upload_store.records[m['job_id']].derived[asset].write_bytes(png(size=(1080,1350),mode='RGB')+b'modified')
    assert c.get(target(b,r)+'/download?format=png&expected_revision=1',headers=h).status_code==409
    assert c.patch(target(b,r),headers=h,json=edit).status_code==409

def test_pdf_completion_checks_current_snapshot_and_busy(service):
    app,c,h,m,b,_,_=service;r,_=prepared(service)
    url=target(b,r)+'/download?format=pdf&expected_revision=1'
    app.state.export_service.pdf_lock.acquire()
    try:assert c.get(url,headers=h).status_code==503
    finally:app.state.export_service.pdf_lock.release()
    def change(_):
        d=draft();d['product_features']='changed during PDF'
        owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
        from app.schemas.upload import InputDraft
        app.state.upload_store.save_draft(owner,m['job_id'],InputDraft.model_validate(d))
        return b'%PDF-test-only'
    app.state.export_service.pdf=change
    assert c.get(url,headers=h).status_code==409
    assert not app.state.upload_store.records[m['job_id']].exports

@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Requires existing Chromium')
def test_actual_edited_png_pdf_and_second_edit(service,tmp_path):
    app,c,h,m,b,body,raw=service
    app.state.render_store.executor=RenderExecution()
    r,edit=prepared(service)
    before=c.get(r['candidates'][0]['png']['url'],headers=h).content
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/editing',headers=h).json()['status']=='completed'
    result=c.get(b+'/rendering',headers=h).json();data=c.get(result['candidates'][0]['png']['url'],headers=h).content
    assert data!=before
    with Image.open(BytesIO(data)) as image:assert image.size==(1080,1350) and image.mode=='RGB'
    pdf=c.get(target(b,r)+'/download?format=pdf&expected_revision=2',headers=h)
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF-')
    assert len(re.findall(rb'/Type\s*/Page\b',pdf.content))==1
    box=re.search(rb'/MediaBox\s*\[([^\]]+)\]',pdf.content)
    coords=[float(x) for x in box[1].split()]
    assert abs(coords[2]*25.4/72-210)<.2 and abs(coords[3]*25.4/72-297)<.2
    assert b'/Width 1080' in pdf.content and b'/Height 1350' in pdf.content
    streams=[]
    for encoded in re.findall(rb'stream\r?\n(.*?)\r?\nendstream',pdf.content,re.S):
        try:streams.append(zlib.decompress(encoded))
        except zlib.error:pass
    # Chromium's lossless RGB image stream must contain exactly the PNG pixels,
    # including Korean glyphs. This checks content, not only the file signature.
    assert Image.open(BytesIO(data)).tobytes() in streams
    drawing=next(s for s in streams if b' Do' in s)
    matrix=re.findall(rb'([\d.]+) 0 0 -([\d.]+) ([\d.]+) ([\d.]+) cm',drawing)[-1]
    w,height,left,bottom=map(float,matrix)
    scale=float(re.search(rb'^([\d.]+) 0 0 -',drawing)[1])
    mm=lambda value:value*scale*25.4/72
    assert abs(w/height-.8)<.00001
    assert mm(left)>=9.9 and 210-mm(left+w)>=9.9
    assert mm(bottom-height)>=29 and 297-mm(bottom)>=29
    (tmp_path/'edited.png').write_bytes(data);(tmp_path/'ad-a4.pdf').write_bytes(pdf.content)
    edit.update(expected_revision=2,copy={**edit['copy'],'headline':'다시 만나는 여유'})
    c.patch(target(b,r),headers=h,json=edit)
    assert c.get(b+'/rendering',headers=h).json()['revision']==3
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==raw
