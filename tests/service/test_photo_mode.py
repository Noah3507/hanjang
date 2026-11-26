from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
import pytest
from PIL import Image
from app.services.render_photo import render_photo
from app.services.uploads import UploadError
from test_rendering import service, draft, fake_render
from test_designs import designs, generate, snap


def normalize(image, side=1600, exif=None):
    stream=BytesIO();image.save(stream,format='PNG',**({'exif':exif} if exif else {}));raw=stream.getvalue()
    upload=SimpleNamespace(asset_id='original',sha256=sha256(raw).hexdigest())
    store=SimpleNamespace(read_asset=lambda owner,asset:(raw,'image/png'))
    return raw,render_photo(store,'owner',SimpleNamespace(upload=upload),upload,SimpleNamespace(photo_mode='original'),side)


def test_rgb_white_composite_no_hidden_rgb_no_upscale():
    image=Image.new('RGBA',(400,300),(0,0,0,0));image.putpixel((10,10),(255,0,0,128))
    raw,result=normalize(image);out=Image.open(BytesIO(result))
    assert out.mode=='RGB' and out.size==(400,300) and out.getpixel((0,0))==(255,255,255)
    assert out.getpixel((10,10))==(255,127,127)
    assert Image.open(BytesIO(raw)).mode=='RGBA'


def test_exif_orientation_and_max_side_preserve_ratio():
    exif=Image.Exif();exif[274]=6
    _,result=normalize(Image.new('RGB',(2400,1200),'red'),exif=exif)
    out=Image.open(BytesIO(result));assert out.size==(800,1600) and out.mode=='RGB'


def test_cutout_reuses_processed_without_changing_analysis_selection():
    raw=b'cached processed bytes';selected=SimpleNamespace(asset_id='original')
    processed=SimpleNamespace(asset_id='processed',sha256=sha256(raw).hexdigest())
    record=SimpleNamespace(photo=SimpleNamespace(processed=processed))
    reads=[]
    def read(owner,asset):reads.append(asset);return raw,'image/png'
    result=render_photo(SimpleNamespace(read_asset=read),'owner',record,selected,SimpleNamespace(photo_mode='cutout'))
    assert result==raw and reads==['processed'] and selected.asset_id=='original'


def test_save_omit_invalid_and_copy_analysis_reuse(service):
    app,c,h,m,b,body,raw=service
    copy=c.get(b+'/copy-generation',headers=h).json()
    old=c.get(b+'/photo-analysis',headers=h).json()
    assert c.get(b+'/input',headers=h).json()['photo_mode']=='cutout'
    d={**draft(),'photo_mode':'original'}
    assert c.put(b+'/input',headers=h,json=d).json()['photo_mode']=='original'
    assert c.put(b+'/input',headers=h,json=draft()).json()['photo_mode']=='original'
    assert c.put(b+'/input',headers=h,json={**d,'photo_mode':'bad'}).status_code==422
    assert c.get(b+'/input').status_code==401
    assert c.get(b+'/copy-generation',headers=h).json()==copy
    assert c.get(b+'/photo-analysis',headers=h).json()==old
    r=c.post(b+'/copy-generation',headers=h,json={k:v for k,v in body.items() if k!='expected_copy_key'}).json();assert r['copy_key']==copy['copy_key']


def test_mode_roundtrip_stale_rank_and_copy_reuse(designs):
    app,c,h,m,b,body,v2=designs;p,s=generate(designs)
    cp=c.get(b+'/copy-generation',headers=h).json()
    assert c.post(p+'/ranking',headers=h,json=snap(s)).status_code==200
    d={**draft(),'photo_mode':'original'};c.put(b+'/input',headers=h,json=d)
    assert c.get(b+'/copy-generation',headers=h).json()==cp
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    state=c.get(p,headers=h).json();assert not state['is_current'] and state['ranking'] is None
    assert c.get(p+'/candidates/'+s['candidates'][0]['candidate_id']+'/download',headers=h,params={'format':'png',**snap(s)}).status_code==409
    assert c.post(b+'/rendering',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':d,'expected_copy_key':cp['copy_key']}).status_code==202
    new=c.get(b+'/rendering',headers=h).json();assert new['is_current'] and new['revision']>v2['revision']
    c.put(b+'/input',headers=h,json={**d,'photo_mode':'cutout'})
    assert c.get(b+'/copy-generation',headers=h).json()==cp
    assert c.get(b+'/rendering',headers=h).json()['is_current']
    assert sha256(c.get('/api/v1/assets/'+m['asset_id'],headers=h).content).hexdigest()==m['sha256']


def test_mode_change_inflight_never_current(service):
    app,c,h,m,b,body,raw=service
    def changed(d,copy,data):
        c.put(b+'/input',headers=h,json={**draft(),'photo_mode':'original'})
        return fake_render(d,copy,data)
    app.state.render_store.executor=changed
    c.post(b+'/rendering',headers=h,json=body)
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    assert c.get(b+'/copy-generation',headers=h).json()['is_current']


def test_expiry_during_photo_snapshot_is_not_swallowed(service,monkeypatch):
    app,c,h,m,b,body,raw=service
    def expired(*args):raise UploadError(410,'JOB_EXPIRED','만료된 작업입니다.')
    monkeypatch.setattr(app.state.render_store,'photo_bytes',expired)
    assert c.get(b+'/rendering',headers=h).status_code==410


def test_v3_edit_mode_change_inflight_preserves_last_assets(designs):
    app,c,h,m,b,body,v2=designs;p,s=generate(designs)
    store=app.state.design_store;executor=store.executor
    def change(data,photo,ids):
        result=executor(data,photo,ids)
        c.put(b+'/input',headers=h,json={**draft(),'photo_mode':'original'})
        return result
    store.executor=change;candidate=s['candidates'][0]
    request={**snap(s),'expected_asset_id':candidate['png']['asset_id'],
             'copy':{**candidate['copy'],'headline':'바뀐 문구'},'price_text':candidate['facts']['price_text']}
    assert c.patch(p+'/candidates/'+candidate['candidate_id'],headers=h,json=request).status_code==202
    latest=c.get(p,headers=h).json()
    assert not latest['is_current'] and latest['ranking'] is None
    assert [v['png']['asset_id'] for v in latest['candidates']]==[v['png']['asset_id'] for v in s['candidates']]
