from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import base64,json,os
from pathlib import Path
from threading import Event,Thread
import pytest
from PIL import Image
from test_rendering import service, fake_render, png, draft
from test_editor import prepared,target
from app.services import diagnostics_engine as e
from app.services.diagnostics_evidence import attach_contrast_evidence,EVIDENCE_VERSION
from app.services.render_execution import RenderExecution
from app.schemas.diagnostics import DiagnosticsRequest
from app.services.uploads import UploadError,now

def candidate():
    return {'candidate_id':'id','strategy':'emotional','png':{'asset_id':'asset'},'renderer':{'text_boxes':[
        {'field':'headline','text':'한 잔의 여유','x':54.,'y':54.,'width':500.,'height':80.,'font_size_px':36.,'font_weight':400,'foreground':'#000000','background':None,'overflow':False}],
        'product_bbox':{'x':54.,'y':500.,'width':500.,'height':400.}}}
def evidence(c,hash='hash'):
    return {'text':[{**t,'contrast_eligible':True,'contrast_evidence':{'version':EVIDENCE_VERSION,'status':'verified','png_sha256':hash,'foreground_rgb':[0,0,0],'background_rgb':[255,255,255]}} for t in c['renderer']['text_boxes']]}
def rules(c=None,m=None,hash='hash'):
    c=c or candidate();return {r.rule_id:r for r in e.analyze(c,m,hash).rules}
def request(r):return {'expected_render_revision':r['revision'],'expected_candidates':[{'candidate_id':c['candidate_id'],'asset_id':c['png']['asset_id']} for c in r['candidates']]}

def test_contrast_known_values_and_symmetry():
    assert e.contrast([0,0,0],[255,255,255])==21
    assert e.contrast([255,255,255],[0,0,0])==21
    assert e.contrast([80,80,80],[80,80,80])==1
    assert e.contrast([119,119,119],[255,255,255])==pytest.approx(4.478089,rel=1e-6)
@pytest.mark.parametrize('color',[[256,0,0],[-1,0,0],[True,0,0],[float('nan'),0,0],[0,0]])
def test_bad_color(color):
    with pytest.raises(ValueError):e.contrast(color,[255,255,255])
@pytest.mark.parametrize('size,weight,threshold',[(24,400,3),(23.99,400,4.5),(14*96/72,700,3),(18,700,4.5)])
def test_large_text_reference(size,weight,threshold):
    c=candidate();c['renderer']['text_boxes'][0].update(font_size_px=size,font_weight=weight)
    r=rules(c,evidence(c))['contrast'];assert r.measured_value['items'][0]['threshold']==threshold
@pytest.mark.parametrize('ratio,status',[(4.5,'normal'),(4.499999,'problem')])
def test_contrast_unrounded_boundary(monkeypatch,ratio,status):
    c=candidate();c['renderer']['text_boxes'][0]['font_size_px']=18
    monkeypatch.setattr(e,'contrast',lambda *a:ratio)
    assert rules(c,evidence(c))['contrast'].status==status
@pytest.mark.parametrize('value',[None,float('nan'),float('inf'),float('-inf'),-1,0,True])
def test_missing_nonfinite_font_not_zero(value):
    c=candidate();c['renderer']['text_boxes'][0]['font_size_px']=value
    r=rules(c)['font_size'];assert r.status=='unavailable' and r.measured_value['minimum'] is None
@pytest.mark.parametrize('size,status',[(36,'normal'),(35.999,'caution')])
def test_font_service_boundary(size,status):
    c=candidate();c['renderer']['text_boxes'][0]['font_size_px']=size
    assert rules(c)['font_size'].status==status
def test_union_excludes_duplicate_and_clips_canvas():
    assert e.union_area([(0,0,100,100),(50,0,100,100),(0,0,100,100)])==15000
    assert e.union_area([(-10,-10,20,20)])==100
@pytest.mark.parametrize('height,status',[(540,'normal'),(541,'caution')])
def test_density_boundary(height,status):
    c=candidate();c['renderer']['text_boxes'][0].update(x=0.,y=0.,width=1080.,height=float(height))
    r=rules(c)['density'];assert r.status==status and r.measured_value['ratio']==height/1350
def test_bbox_crossing_caution_not_error_and_clear_bounds_problem():
    c=candidate();t=c['renderer']['text_boxes'][0];c['renderer']['text_boxes'].append({**t,'field':'body','x':60.})
    assert rules(c)['layout'].status=='caution'
    c['renderer']['text_boxes'][1]['x']=-1
    assert rules(c)['layout'].status=='problem'
def test_overflow_only_caution_and_bad_geometry_partial():
    c=candidate();c['renderer']['text_boxes'][0]['overflow']=True
    assert rules(c)['layout'].status=='caution'
    c['renderer']['text_boxes'].append({'field':'body','x':float('nan')})
    r=rules(c);assert r['layout'].coverage=='partial' and r['density'].coverage=='partial'
    assert r['density'].measured_value['ratio']>0
def test_missing_metadata_never_all_normal_and_partial_rule_failure(monkeypatch):
    c=candidate();r=rules(c)
    assert r['contrast'].status=='unavailable' and r['font_size'].status=='normal'
    monkeypatch.setattr(e,'fonts',lambda *a:(_ for _ in ()).throw(RuntimeError('private path')))
    r=rules(c);assert r['font_size'].status=='unavailable' and r['density'].measured_value['ratio']>0
    c['renderer']={};assert all(r.status=='unavailable' for r in rules(c).values())
def test_css_color_without_pixel_proof_or_wrong_binding_unavailable():
    c=candidate();c['renderer']['text_boxes'][0]['background']='#FFFFFF'
    assert rules(c)['contrast'].measured_value['minimum'] is None
    m=evidence(c);assert rules(c,m,'different-png')['contrast'].status=='unavailable'
    m['text'][0]['contrast_eligible']=False;assert rules(c,m)['contrast'].status=='unavailable'
def test_heuristic_constants_are_adjustable(monkeypatch):
    monkeypatch.setattr(e,'SMALL_FONT_PX',40.)
    monkeypatch.setattr(e,'DENSITY_LIMIT',.01)
    r=rules();assert r['font_size'].status=='caution' and r['density'].status=='caution'
def test_uniform_background_capture_and_nonuniform_or_unsupported():
    raw=png(size=(1080,1350));bg=base64.b64encode(raw).decode()
    def result(eligible=True):return {'png':raw,'background_png':bg,'measurement':{'text':[{'foreground':'rgb(0, 0, 0)','contrast_eligible':eligible,'glyph_rects':[{'x':10.,'y':10.,'width':100.,'height':100.}]}]}}
    r=result();attach_contrast_evidence(r)
    assert r['measurement']['text'][0]['contrast_evidence']['status']=='verified' and 'background_png' not in r
    r=result(False);attach_contrast_evidence(r);assert r['measurement']['text'][0]['contrast_evidence']['status']=='unavailable'
    im=Image.open(BytesIO(raw));im.putpixel((20,20),(0,0,0));out=BytesIO();im.save(out,'PNG')
    r=result();r['background_png']=base64.b64encode(out.getvalue()).decode();attach_contrast_evidence(r)
    assert r['measurement']['text'][0]['contrast_evidence']['status']=='unavailable'

def test_sync_api_cache_preserves_render_ranking_original_and_contract(service):
    app,c,h,m,b,body,raw=service;r,_=prepared(service)
    assert c.get(b+'/diagnostics',headers=h).json()['status']=='pending'
    c.post(b+'/ranking',headers=h,json={'expected_render_revision':r['revision'],'expected_candidate_ids':[v['candidate_id'] for v in r['candidates']]})
    ranking=c.get(b+'/ranking',headers=h).json();calls=[];original=app.state.diagnostics_store.analyzer
    def counted(*a):calls.append(1);return original(*a)
    app.state.diagnostics_store.analyzer=counted
    response=c.post(b+'/diagnostics',headers=h,json=request(r));assert response.status_code==200 and 'location' not in response.headers
    data=response.json();assert data['status']=='completed' and data['is_current'] and len(data['results'])==4
    assert all(x['coverage']=='partial' for x in data['results']) # fake renderer has no pixel evidence
    assert c.post(b+'/diagnostics',headers=h,json=request(r)).json()==data and len(calls)==4
    assert c.get(b+'/diagnostics',headers=h).json()==data
    assert c.get(b+'/rendering',headers=h).json()==r and c.get(b+'/ranking',headers=h).json()==ranking
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==raw
    assert c.get(b+'/input',headers=h).json()['status']=='pending'
    assert not app.state.render_store.active
    from jsonschema import validate
    validate({'candidates':r['candidates']},json.loads(Path('tests/fixtures/contracts/candidates.schema.json').read_text()))

def test_auth_validation_conflicts_and_expiry(service):
    app,c,h,m,b,_,_=service;r,_=prepared(service);req=request(r)
    assert c.post(b+'/diagnostics',json=req).status_code==401
    other={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
    assert c.post(b+'/diagnostics',headers=other,json=req).status_code==404
    assert c.get(b+'/diagnostics',headers=other).status_code==404
    assert c.post(b+'/diagnostics',headers=h,json={**req,'expected_render_revision':99}).status_code==409
    bad=deepcopy(req);bad['expected_candidates'][0]['asset_id']='0'*32
    assert c.post(b+'/diagnostics',headers=h,json=bad).status_code==409
    bad=deepcopy(req);bad['expected_candidates'][0]=bad['expected_candidates'][1]
    assert c.post(b+'/diagnostics',headers=h,json=bad).status_code==422
    assert c.post(b+'/diagnostics',headers=h,content=b'x'*17000).status_code==413
    c.post(b+'/diagnostics',headers=h,json=req);record=app.state.upload_store.records[m['job_id']]
    record.upload.expires_at=now()-timedelta(seconds=1);app.state.upload_store.cleanup()
    assert record.diagnostic_result is None and c.get(b+'/diagnostics',headers=h).status_code in (404,410)

@pytest.mark.parametrize('mode',['missing','changed','corrupt','wrong_size','wrong_mode'])
def test_invalid_asset_is_not_reported_normal(service,mode):
    app,c,h,m,b,_,_=service;r,_=prepared(service);asset=r['candidates'][0]['png']['asset_id'];record=app.state.upload_store.records[m['job_id']];p=record.derived[asset]
    if mode=='missing':p.unlink()
    elif mode=='changed':p.write_bytes(p.read_bytes()+b'different')
    elif mode=='corrupt':p.write_bytes(b'not PNG')
    elif mode=='wrong_size':p.write_bytes(png(size=(200,200)))
    else:p.write_bytes(png(mode='L',size=(1080,1350)))
    assert c.post(b+'/diagnostics',headers=h,json=request(r)).status_code in (404,409)
    assert record.diagnostic_result is None

def test_failed_diagnosis_retry_and_edit_staleness(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service);store=app.state.diagnostics_store;analyze=store.analyzer
    store.analyzer=lambda *a:(_ for _ in ()).throw(RuntimeError('private error'))
    failed=c.post(b+'/diagnostics',headers=h,json=request(r));assert failed.status_code==200 and failed.json()['status']=='failed'
    assert 'private' not in failed.text and c.get(b+'/rendering',headers=h).json()==r
    store.analyzer=analyze;c.post(b+'/diagnostics',headers=h,json=request(r))
    executor=app.state.render_store.executor
    app.state.render_store.executor=lambda *a:(_ for _ in ()).throw(RuntimeError())
    c.patch(target(b,r),headers=h,json=edit);assert c.get(b+'/diagnostics',headers=h).json()['is_current']
    app.state.render_store.executor=executor;c.patch(target(b,r),headers=h,json=edit)
    assert not c.get(b+'/diagnostics',headers=h).json()['is_current']
    latest=c.get(b+'/rendering',headers=h).json()
    assert c.post(b+'/diagnostics',headers=h,json=request(r)).status_code==409
    assert c.post(b+'/diagnostics',headers=h,json=request(latest)).json()['revision']==latest['revision']

def test_rule_configuration_change_invalidates_cached_diagnosis(service,monkeypatch):
    _,c,h,_,b,_,_=service;r,_=prepared(service)
    c.post(b+'/diagnostics',headers=h,json=request(r))
    monkeypatch.setattr(e,'SMALL_FONT_PX',40.)
    assert not c.get(b+'/diagnostics',headers=h).json()['is_current']
    result=c.post(b+'/diagnostics',headers=h,json=request(r)).json()
    assert result['is_current'] and '40 PNG px' in result['results'][0]['rules'][1]['criterion']

def test_missing_measurements_preserves_other_measured_rules(service):
    app,c,h,m,b,_,_=service;r,_=prepared(service)
    record=app.state.upload_store.records[m['job_id']]
    record.renders[record.last_render].measurements={}
    result=c.post(b+'/diagnostics',headers=h,json=request(r)).json()
    assert result['status']=='completed' and result['results'][0]['coverage']=='partial'
    rules={x['rule_id']:x for x in result['results'][0]['rules']}
    assert rules['contrast']['measured_value']['minimum'] is None
    assert rules['font_size']['measured_value']['minimum']==32

def test_input_changed_during_calculation_is_consistent_conflict(service):
    app,c,h,m,b,_,raw=service;r,_=prepared(service);store=app.state.diagnostics_store;analyzer=store.analyzer
    def change(*args):
        d=draft();d['product_features']='changed input'
        c.put(b+'/input',headers=h,json=d)
        return analyzer(*args)
    store.analyzer=change
    response=c.post(b+'/diagnostics',headers=h,json=request(r))
    assert response.status_code==409 and response.json()['error']['code']=='DIAGNOSTICS_SOURCE_CHANGED'
    assert not store.busy and app.state.upload_store.records[m['job_id']].diagnostic_result is None
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==raw

def test_concurrent_duplicate_and_late_result_cannot_publish(service):
    app,c,h,m,b,_,_=service;r,edit=prepared(service);store=app.state.diagnostics_store
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);entered=Event();release=Event();original=store.analyzer;errors=[]
    def blocking(*a):entered.set();assert release.wait(15);return original(*a)
    store.analyzer=blocking
    def run():
        try:store.run(owner,m['job_id'],DiagnosticsRequest.model_validate(request(r)))
        except UploadError as err:errors.append(err)
    worker=Thread(target=run);worker.start()
    try:
        assert entered.wait(5)
        assert c.get(b+'/diagnostics',headers=h).json()['status']=='processing'
        assert c.post(b+'/diagnostics',headers=h,json=request(r)).status_code==503
        assert not app.state.render_store.active
        c.patch(target(b,r),headers=h,json=edit)
    finally:release.set();worker.join(15)
    assert not worker.is_alive() and errors[0].code=='DIAGNOSTICS_SOURCE_CHANGED'
    assert not store.busy and app.state.upload_store.records[m['job_id']].diagnostic_result is None
    store.analyzer=original;latest=c.get(b+'/rendering',headers=h).json()
    assert c.post(b+'/diagnostics',headers=h,json=request(latest)).json()['is_current']

@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Requires installed Chromium')
def test_real_contrast_evidence_edit_and_pdf_contract(service):
    app,c,h,m,b,body,raw=service;app.state.render_store.executor=RenderExecution();r,edit=prepared(service)
    result=c.post(b+'/diagnostics',headers=h,json=request(r)).json()
    assert result['status']=='completed'
    for candidate_result in result['results']:
        contrast=next(x for x in candidate_result['rules'] if x['rule_id']=='contrast')
        assert contrast['coverage']=='complete' and contrast['measured_value']['minimum']>3
    before=c.get('/api/v1/assets/'+m['asset_id'],headers=h).content
    c.patch(target(b,r),headers=h,json=edit);assert not c.get(b+'/diagnostics',headers=h).json()['is_current']
    new=c.get(b+'/rendering',headers=h).json();diag=c.post(b+'/diagnostics',headers=h,json=request(new)).json()
    assert diag['revision']==new['revision'] and diag['is_current']
    assert all(next(r for r in item['rules'] if r['rule_id']=='contrast')['coverage']=='complete' for item in diag['results'])
    assert c.get(target(b,new)+'/download?format=pdf&expected_revision='+str(new['revision']),headers=h).status_code==200
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content==before==raw

@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Requires installed Chromium')
@pytest.mark.parametrize('css',['.ad{background:linear-gradient(white,#999)}','.ad{opacity:.8}'])
def test_real_unsupported_paint_never_guesses_contrast(service,monkeypatch,css):
    app,c,h,_,b,_,_=service;original=Path.read_text
    def read(path,*args,**kw):
        value=original(path,*args,**kw)
        return value+'\n'+css if path.name=='tokens.css' else value
    monkeypatch.setattr(Path,'read_text',read)
    app.state.render_store.executor=RenderExecution();r,_=prepared(service)
    result=c.post(b+'/diagnostics',headers=h,json=request(r)).json()
    assert result['status']=='completed'
    for candidate_result in result['results']:
        r=next(x for x in candidate_result['rules'] if x['rule_id']=='contrast')
        assert r['status']=='unavailable' and r['measured_value']['minimum'] is None
        assert next(x for x in candidate_result['rules'] if x['rule_id']=='font_size')['measured_value']['minimum']>0
