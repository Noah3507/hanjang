from datetime import timedelta
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.schemas.upload import InputDraft
from app.schemas.rendering import RenderRequest
from app.services.render_execution import RenderExecution, RenderFailure, ORDERS, opaque_png
from app.services.uploads import now, UploadError

def png(mode='RGB', size=(400,300)):
    stream=BytesIO(); Image.new(mode,size,'orange').save(stream,'PNG'); return stream.getvalue()

def draft(address=None, instagram=None):
    return {'facts':{'store_name':'  쿠지라스토랑  ','product_name':'아부라소바','price_text':' 10,500 원 ',
        'address':address,'instagram_handle':instagram},'mood':'warm','product_features':'특제 소스','use_address_for_copy':False}

def fake_render(draft, copy, data):
    # Synthetic geometry for Store/API tests, never presented as actual browser evidence.
    results=[]
    for i, v in enumerate(copy.variants):
        texts={**draft.facts.model_dump(),**v.ad_copy.model_dump()}
        results.append({'strategy':v.strategy,'png':png(size=(1080,1350)), 'measurement':{
            'text':[{'field':k,'text':t,'x':54.,'y':float(54+j*48),'width':972.,'height':48.,'font_size_px':32.,'font_weight':400,
                'foreground':'rgb(36, 37, 33)','background':'rgba(0, 0, 0, 0)','overflow':False,'line_count':1,'font_family':'fake','actual_fonts':[]} for j,(k,t) in enumerate(texts.items()) if t],
            'product':{'x':54.,'y':600.,'width':400.,'height':300.},'layout':'fake'}})
    return results

@pytest.fixture
def service(tmp_path):
    app=create_app(Settings(_env_file=None,upload_root=tmp_path/'uploads'))
    app.state.render_store.executor=fake_render
    with TestClient(app) as client:
        h={'X-Hanjang-Session':client.post('/api/v1/sessions').json()['session_token']}
        raw=png(); meta=client.post('/api/v1/uploads',headers=h,files={'photo':('test.png',raw,'image/png')}).json()
        base=f'/api/v1/jobs/{meta["job_id"]}'
        client.put(base+'/input',headers=h,json=draft())
        client.post(base+'/copy-generation',headers=h,json={'expected_asset_id':meta['asset_id'],'expected_input':draft()})
        copy=client.get(base+'/copy-generation',headers=h).json()
        body={'expected_asset_id':meta['asset_id'],'expected_input':draft(),'expected_copy_key':copy['copy_key']}
        yield app,client,h,meta,base,body,raw

def test_four_candidates_contract_cache_and_original(service):
    app,c,h,m,b,body,raw=service
    first=c.post(b+'/rendering',headers=h,json=body)
    assert first.status_code==202 and first.headers['Location']==b+'/rendering'
    result=c.get(b+'/rendering',headers=h).json()
    assert result['status']=='completed' and result['is_current'] and result['mock_copy']
    from jsonschema import validate
    schema=json.loads(Path('tests/fixtures/contracts/candidates.schema.json').read_text())
    validate({'candidates':result['candidates']},schema)
    assert len({v['candidate_id'] for v in result['candidates']})==4
    for v in result['candidates']:
        assert v['facts']==draft()['facts'] and v['revision']==v['png']['revision']==result['revision']
        response=c.get(v['png']['url'],headers=h);assert response.status_code==200
        with Image.open(BytesIO(response.content)) as im: assert im.mode=='RGB' and im.size==(1080,1350)
    assert c.post(b+'/rendering',headers=h,json=body).json()['candidates']==result['candidates']
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==raw
    assert c.get(b+'/copy-generation',headers=h).json()['copy_key']==body['expected_copy_key']

@pytest.mark.parametrize('field',['expected_asset_id','expected_copy_key','expected_input'])
def test_snapshot_conflict(service,field):
    _,c,h,_,b,body,_=service
    if field=='expected_input': body[field]['product_features']='바뀐 특징'
    else: body[field]='0'*32
    assert c.post(b+'/rendering',headers=h,json=body).status_code==409

def test_stale_reuse_and_revision(service):
    app,c,h,m,b,body,_=service
    c.post(b+'/rendering',headers=h,json=body)
    first=c.get(b+'/rendering',headers=h).json()
    changed=draft();changed['product_features']='새 특징'
    c.put(b+'/input',headers=h,json=changed)
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    assert c.post(b+'/rendering',headers=h,json=body).status_code==409
    copybody={'expected_asset_id':m['asset_id'],'expected_input':changed}
    c.post(b+'/copy-generation',headers=h,json=copybody)
    newcopy=c.get(b+'/copy-generation',headers=h).json()
    assert newcopy['copy_key']!=body['expected_copy_key']
    c.post(b+'/rendering',headers=h,json={**copybody,'expected_copy_key':newcopy['copy_key']})
    latest=c.get(b+'/rendering',headers=h).json()
    assert latest['revision']==2 and latest['is_current'] and latest['candidates']!=first['candidates']

def test_change_during_render_kept_stale(service):
    app,c,h,m,b,body,_=service
    def changed(d,copy,data):
        owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
        value=d.model_copy(update={'product_features':'changed'})
        app.state.upload_store.save_draft(owner,m['job_id'],value)
        return fake_render(d,copy,data)
    app.state.render_store.executor=changed
    c.post(b+'/rendering',headers=h,json=body)
    response=c.get(b+'/rendering',headers=h).json()
    assert response['status']=='completed' and not response['is_current']

@pytest.mark.parametrize('code',['RENDER_TIMEOUT','RENDER_FAILED','RENDER_LAYOUT_OVERFLOW'])
def test_failure_cleanup_and_retry(service,code):
    app,c,h,m,b,body,_=service
    def fail(*args): raise RenderFailure(code)
    app.state.render_store.executor=fail
    c.post(b+'/rendering',headers=h,json=body)
    result=c.get(b+'/rendering',headers=h).json()
    assert result['status']=='failed' and result['error']['code']==code and not result['candidates']
    assert len(list(app.state.upload_store.root.iterdir()))==1
    app.state.render_store.executor=fake_render
    c.post(b+'/rendering',headers=h,json=body)
    assert c.get(b+'/rendering',headers=h).json()['status']=='completed'

def test_private_expiry_paths_and_body_limit(service):
    app,c,h,m,b,body,_=service
    assert c.get(b+'/rendering').status_code==401
    other={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
    assert c.get(b+'/rendering',headers=other).status_code==404
    c.post(b+'/rendering',headers=h,json=body)
    result=c.get(b+'/rendering',headers=h).json()
    assert c.get(result['candidates'][0]['png']['url'],headers=other).status_code==404
    assert c.post(b+'/rendering',headers=h,content=b'x'*16385).status_code==413
    with pytest.raises(UploadError): app.state.upload_store.safe_path('../outside.png')
    record=app.state.upload_store.records[m['job_id']]
    record.upload.expires_at=now()-timedelta(seconds=1)
    assert c.get(result['candidates'][0]['png']['url'],headers=h).status_code==410
    app.state.upload_store.cleanup(); assert not list(app.state.upload_store.root.iterdir())

def test_inflight_dedup_busy_and_no_copy(service):
    app,c,h,m,b,body,_=service
    store=app.state.render_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    first,task=store.start(owner,m['job_id'],RenderRequest.model_validate(body))
    second,none=store.start(owner,m['job_id'],RenderRequest.model_validate(body))
    assert none is None and second.copy_key==first.copy_key
    store.finish(owner,m['job_id'],task)
    app.state.upload_store.records[m['job_id']].copies.clear()
    assert c.post(b+'/rendering',headers=h,json=body).status_code==409

def test_partial_publication_failure_removes_all_written_pngs(service,monkeypatch):
    import app.services.render_store as module
    app,c,h,m,b,body,_=service
    real=module.os.open
    calls=0
    def fail_second(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2: raise OSError('synthetic disk full')
        return real(*args,**kwargs)
    monkeypatch.setattr(module.os,'open',fail_second)
    c.post(b+'/rendering',headers=h,json=body)
    result=c.get(b+'/rendering',headers=h).json()
    assert result['status']=='failed' and result['candidates']==[]
    assert len(list(app.state.upload_store.root.iterdir()))==1
    assert app.state.upload_store.records[m['job_id']].derived=={}

def test_photo_change_during_render_is_stale(service):
    from app.schemas.photo import PhotoAsset
    app,c,h,m,b,body,_=service
    def change(d,copy,data):
        owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
        store=app.state.upload_store;store.photo_state(owner,m['job_id'])
        record=store.get(owner,m['job_id'])
        record.photo.processed=PhotoAsset(asset_id='a'*32,width=400,height=300,mime_type='image/png',sha256='b'*64)
        record.photo.photo_source='processed'
        return fake_render(d,copy,data)
    app.state.render_store.executor=change
    c.post(b+'/rendering',headers=h,json=body)
    response=c.get(b+'/rendering',headers=h).json()
    assert response['status']=='completed' and not response['is_current']

def test_existing_control_character_contract_stays_strict(service):
    _,c,h,_,b,_,_=service
    value=draft();value['facts']['store_name']='가게\n이름'
    assert c.put(b+'/input',headers=h,json=value).status_code==422

@pytest.mark.parametrize('data',[png(size=(10,10)),png('RGBA',size=(1080,1350)),b'invalid'])
def test_bad_png(data):
    if data.startswith(b'\x89PNG'):
        with Image.open(BytesIO(data)) as im:
            if im.mode=='RGBA':
                im.putalpha(0);b=BytesIO();im.save(b,'PNG');data=b.getvalue()
    with pytest.raises(Exception): opaque_png(data)

# Real browser rendering is opt-in; CI browser-e2e job installs Chromium first.
@pytest.mark.skipif(os.environ.get('RUN_RENDER_TESTS')!='1',reason='requires installed Node/Playwright Chromium; run RUN_RENDER_TESTS=1')
@pytest.mark.parametrize('case',['normal','copy_max','no_space_ko','spaced_ko','english','mixed','empty_body','empty_cta','empty_both','long_store','long_product','long_price','address','instagram','both_contacts','html','transparent','extreme'])
def test_actual_browser_boundaries(case,tmp_path):
    d=InputDraft.model_validate(draft())
    text={'headline':'한 끼의 여유','body':'오늘의 시간을 즐겨보세요.','cta':'만나보세요'}
    if case=='copy_max': text={'headline':'한'*60,'body':'문'*160,'cta':'가'*30}
    if case=='no_space_ko': text={'headline':'한'*60,'body':'식'*160,'cta':'나'*30}
    if case=='spaced_ko': text={'headline':('한글 문장 '*10)[:60],'body':('긴 문장을 읽어보세요. '*14)[:160],'cta':'매장에서 만나보세요'}
    if case=='english': text={'headline':'W'*60,'body':'W'*160,'cta':'W'*30}
    if case=='mixed': text={'headline':('한A1! '*12),'body':('한글 test 123! '*12)[:160],'cta':'더 만나보세요!'}
    if case in ('empty_body','empty_both'): text['body']=''
    if case in ('empty_cta','empty_both'): text['cta']=''
    if case=='long_store': d.facts.store_name='가'*80
    if case=='long_product': d.facts.product_name='상'*80
    if case=='long_price': d.facts.price_text='일'*40
    if case in ('address','both_contacts'): d.facts.address='주'*200
    if case in ('instagram','both_contacts'): d.facts.instagram_handle='계'*80
    if case=='html': d.facts.store_name='<script>alert("x")</script> & <b>가게</b>'
    if case=='extreme':
        d.facts.store_name='가'*80;d.facts.product_name='나'*80;d.facts.price_text='다'*40
        d.facts.address='라'*200;d.facts.instagram_handle='마'*80
        text={'headline':'바'*60,'body':'사'*160,'cta':'아'*30}
    variants=[SimpleNamespace(strategy=s,ad_copy=SimpleNamespace(model_dump=lambda:text)) for s in ORDERS]
    source=png('RGBA')
    if case=='transparent':
        from PIL import ImageDraw
        image=Image.new('RGBA',(400,300),(0,0,0,0));ImageDraw.Draw(image).rectangle((30,30,370,270),fill='orange')
        stream=BytesIO();image.save(stream,'PNG');source=stream.getvalue()
    if case=='extreme':
        with pytest.raises(RenderFailure,match='RENDER_LAYOUT_OVERFLOW'):
            RenderExecution()(d,SimpleNamespace(variants=variants),source)
        return
    results=RenderExecution()(d,SimpleNamespace(variants=variants),source)
    frames=[]
    for r in results:
        with Image.open(BytesIO(r['png'])) as im: assert im.mode=='RGB' and im.size==(1080,1350)
        m=r['measurement'];assert not m['invalid']
        frames.append(m['photo_frame'])
        fields={b['field']:b for b in m['text']}
        for name in ('store_name','product_name','price_text'):
            assert fields[name]['text']==getattr(d.facts,name)
        assert ('body' in fields)==bool(text['body']) and ('cta' in fields)==bool(text['cta'])
        for b in m['text']:
            assert not b['overflow'] and b['font_size_px']>=32
            assert all(f['isCustomFont'] for f in b['actual_fonts'])
        assert m['product']['width']/m['product']['height']==pytest.approx(4/3)
        (tmp_path/(r['strategy']+'.png')).write_bytes(r['png'])
    assert len({json.dumps(f,sort_keys=True) for f in frames})>=3
