"""Local reviewed backgrounds; store tests fake rendering, Chromium is opt-in."""
from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import json,os
from pathlib import Path
import pytest
from PIL import Image

from app.services.background_art_direction import BackgroundLibrary,prompt_plan,VERSION
from app.services.template_v3 import TemplateInput,render_templates
from app.services.render_execution import RenderFailure
from app.services.uploads import UploadError
from app.schemas.designs import DesignSnapshot
from test_rendering import service
from test_designs import designs,generate,snap


@pytest.fixture
def plates(tmp_path):
    path=tmp_path/'bg.png';im=Image.new('RGB',(512,768),'#d9c5ad');im.save(path)
    item={'file':'bg.png','sha256':sha256(path.read_bytes()).hexdigest(),'reviewed':True,
          'model':'local-fixture','prompt_version':'fixture1','templates':['visual_a','visual_d','emotional_a']}
    return BackgroundLibrary(tmp_path,{'plate':item}),path


def test_assets_are_verified_scoped_and_payload_excludes_fact_text(plates):
    library,path=plates
    ctx=library.context('owner','job',datetime.now(timezone.utc),{'visual_a':'plate'})
    snapshot=ctx.snapshot()
    assert snapshot['owner']=='owner' and snapshot['job']=='job' and snapshot['version']==VERSION
    assert 'png_base64' not in json.dumps(snapshot)
    assert ctx.worker_pages(['visual_a'])['visual_a']['png_base64']
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):library.context('owner','job',datetime.now(timezone.utc),{'visual_a':'plate'})
    assert ctx.worker_pages(['visual_a'])  # immutable bytes keep a previous successful selection usable


@pytest.mark.parametrize('updates',[{'reviewed':False},{'file':'../outside.png'},{'sha256':'wrong'},
                                 {'templates':['brand_a']}])
def test_unreviewed_traversal_corruption_and_compatibility_rejected(plates,updates):
    library,_=plates;library.manifest['plate'].update(updates)
    with pytest.raises((ValueError,OSError)):library.context('o','j',datetime.now(timezone.utc),{'visual_a':'plate'})


def test_prompt_has_only_enum_palette_geometry_not_user_copy():
    m={'product':{'x':100,'y':200,'width':700,'height':600},'text':[{'x':70,'y':1050,'width':900,'height':80,'text':'DO NOT SEND PRIVATE FACTS'}]}
    plan=prompt_plan('coffee','visual','menu_promotion',m,['#D9C5AD'])
    assert 'PRIVATE FACTS' not in plan['prompt'] and plan['spec']['category_confirmed'] is False
    assert plan['spec']['contact_y']==800
    assert plan['spec']['generation_canvas']==[1024,1536]
    region=plan['spec']['source_product_region']
    assert 0<=region['y']<1536 and region['y']+region['height']<=1536
    for args in [('private shop','visual','order'),('coffee','brand','order'),('coffee','visual','invented')]:
        with pytest.raises(ValueError):prompt_plan(*args,m,['#D9C5AD'])
    with pytest.raises(ValueError):prompt_plan('coffee','visual','order',m,['send secret'])


def test_select_edit_stale_and_no_new_copy(designs,plates,monkeypatch):
    app,c,h,meta,base,body,v2=designs;path,state=generate(designs,'visual')
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);store=app.state.design_store
    store.background_library=plates[0]
    before=c.get(base+'/copy-generation',headers=h).json()
    monkeypatch.setattr(app.state.copy_store.provider,'generate',lambda *a:pytest.fail('No generation for background/edits'))
    assert c.post(path+'/ranking',headers=h,json=snap(state)).status_code==200
    updated=store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    assert updated.is_current and updated.revision==state['revision']+1 and updated.ranking is None
    context=app.state.upload_store.get(owner,meta['job_id']).background_context
    assert context.selections()=={'visual_a':'plate'}
    first=updated.candidates[0]
    patch={**snap(updated.model_dump()),'expected_asset_id':first.png.asset_id,'copy':{'headline':'바뀐 문구','body':'','cta':''},'price_text':'12,000원'}
    assert c.patch(path+'/candidates/'+first.candidate_id,headers=h,json=patch).status_code==202
    assert app.state.upload_store.get(owner,meta['job_id']).background_context is context
    assert c.get(base+'/copy-generation',headers=h).json()==before
    assert c.get(base+'/rendering',headers=h).json()==v2
    assert c.get(path+'/candidates/'+state['candidates'][0]['candidate_id']+'/download',headers=h,params={'format':'png',**snap(state)}).status_code==409
    edited=c.get(path,headers=h).json()
    cleared=store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(edited)),{})
    assert cleared.candidates[0].facts.price_text=='12,000원'
    assert cleared.candidates[0].ad_copy.headline=='바뀐 문구'
    assert cleared.candidates[1].facts.price_text==state['candidates'][1]['facts']['price_text']


def test_background_failure_restores_previous_success_and_permissions(designs,plates,monkeypatch):
    app,c,h,meta,base,body,v2=designs;path,state=generate(designs,'visual')
    store=app.state.design_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);store.background_library=plates[0]
    def fail(*a):raise RenderFailure('RENDER_FAILED')
    monkeypatch.setattr(store,'executor',fail)
    with pytest.raises(UploadError,match='이전 광고'):
        store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    assert c.get(path,headers=h).json()==state
    assert app.state.upload_store.get(owner,meta['job_id']).background_context is None
    with pytest.raises(UploadError):store.apply_background('other',meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    plates[1].write_bytes(b'corrupt')
    with pytest.raises(UploadError):store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    assert c.get(path,headers=h).json()==state


def test_original_keeps_plain_card_and_remembers_cutout_selection(designs,plates):
    from test_rendering import draft
    app,c,h,meta,base,body,v2=designs;path,state=generate(designs,'visual')
    store=app.state.design_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);store.background_library=plates[0]
    store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    context=app.state.upload_store.get(owner,meta['job_id']).background_context
    changed={**draft(),'photo_mode':'original'}
    assert c.put(base+'/input',headers=h,json=changed).status_code==200
    cp=c.get(base+'/copy-generation',headers=h).json()
    assert c.post(base+'/rendering',headers=h,json={'expected_asset_id':meta['asset_id'],'expected_input':changed,'expected_copy_key':cp['copy_key']}).status_code==202
    source=c.get(base+'/rendering',headers=h).json()
    assert c.post(path,headers=h,json={'expected_render_revision':source['revision'],'expected_source_asset_id':meta['asset_id'],'expected_copy_key':cp['copy_key']}).status_code==202
    current=c.get(path,headers=h).json()
    entry=app.state.upload_store.get(owner,meta['job_id']).design_sets['visual']
    assert all(data.background_context is None for data in entry.inputs.values())
    assert app.state.upload_store.get(owner,meta['job_id']).background_context is context
    with pytest.raises(UploadError) as error:store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(current)),{'visual_a':'plate'})
    assert error.value.status==422


def test_expiry_and_late_input_change_cannot_publish_background(designs,plates,monkeypatch):
    from datetime import timedelta
    from app.services.uploads import now
    from test_rendering import draft
    app,c,h,meta,base,body,v2=designs;path,state=generate(designs,'visual')
    store=app.state.design_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);store.background_library=plates[0]
    original=store.executor
    def changed(*args):
        result=original(*args)
        assert c.put(base+'/input',headers=h,json={**draft(),'product_features':'바뀐 특징'}).status_code==200
        return result
    monkeypatch.setattr(store,'executor',changed)
    with pytest.raises(UploadError):store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    latest=c.get(path,headers=h).json()
    assert not latest['is_current'] and latest['ranking'] is None
    assert [r['png']['asset_id'] for r in latest['candidates']]==[r['png']['asset_id'] for r in state['candidates']]
    record=app.state.upload_store.get(owner,meta['job_id']);record.upload.expires_at=now()-timedelta(seconds=1)
    with pytest.raises(UploadError) as error:store.apply_background(owner,meta['job_id'],'visual',DesignSnapshot(**snap(state)),{'visual_a':'plate'})
    assert error.value.status==410


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_directed_chromium_preserves_photo_geometry_text_and_snapshot(plates):
    context=plates[0].context('owner','job',datetime.now(timezone.utc),{'visual_a':'plate'})
    photo=Image.new('RGBA',(400,300),(200,70,20,0));photo.paste((200,70,20,255),(30,30,370,270))
    buffer=BytesIO();photo.save(buffer,'PNG');raw=buffer.getvalue()
    data=TemplateInput('가게','상품','10,500원','오늘의 선택','','')
    old=render_templates(data,raw,['visual_a'])[0]
    new=render_templates(replace(data,background_context=context),raw,['visual_a'])[0]
    assert old['input_snapshot']!=new['input_snapshot'] and old['png_sha256']!=new['png_sha256']
    assert old['measurement']['product']==new['measurement']['product']
    assert [(t['field'],t['text'],t['font_size_px']) for t in old['measurement']['text']]==[(t['field'],t['text'],t['font_size_px']) for t in new['measurement']['text']]
    composition=new['measurement']['background_composition']
    assert composition['policy']=='directed' and composition['sha256']==context.pages[0].sha256
    assert composition['quiet_bands'] and not new['measurement']['text_collisions']
