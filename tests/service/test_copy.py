from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.config import Settings
from app.main import create_app
from app.schemas.upload import InputDraft
from app.schemas.copy import CopyRequest
from app.services.copy_provider import MockCopyProvider, OpenAICopyProvider, ProviderResult
from app.services.copy_prompt import provider_payload
from app.services.copy_validation import validate_copy, CopyFailure
from app.services.copy_budget import CopyBudget, MAX_COST
from app.services.uploads import now

def draft(**extras):
    return {'facts': {'store_name': '  테스트 가게  ', 'product_name': '한글 상품', 'price_text': ' 10,500 원 ', 'address': '비공개 주소 123', 'instagram_handle': 'private-insta'}, 'mood': 'warm', **extras}

@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(_env_file=None, upload_root=tmp_path/'uploads', copy_budget_path=tmp_path/'ledger.json'))
    with TestClient(app) as client:
        headers = {'X-Hanjang-Session': client.post('/api/v1/sessions').json()['session_token']}
        stream = BytesIO(); Image.new('RGB', (300, 300), 'orange').save(stream, 'PNG')
        raw = stream.getvalue()
        meta = client.post('/api/v1/uploads', headers=headers, files={'photo': ('a.png', raw, 'image/png')}).json()
        path = f'/api/v1/jobs/{meta["job_id"]}/copy-generation'
        yield app, client, headers, meta, path, raw

def save(client, headers, path, value=None):
    value = draft() if value is None else value
    response = client.put(path.replace('copy-generation', 'input'), headers=headers, json=value)
    assert response.status_code == 200
    return response.json()

def request(meta, value=None):
    return {'expected_asset_id': meta['asset_id'], 'expected_input': draft() if value is None else value}

def test_optional_features_legacy_omission_and_explicit_clear(setup):
    app, client, headers, meta, path, raw = setup
    initial = save(client, headers, path)
    assert initial['product_features'] is None and initial['use_address_for_copy'] is False
    text = '  바삭한 식감\r\n우유 사용  '
    value = draft(product_features=text, use_address_for_copy=True)
    assert save(client, headers, path, value)['product_features'] == text
    legacy = draft(); legacy['mood'] = 'premium'
    saved = save(client, headers, path, legacy)
    assert saved['product_features'] == text and saved['use_address_for_copy'] is True
    cleared = save(client, headers, path, draft(product_features=None, use_address_for_copy=False))
    assert cleared['product_features'] is None and cleared['use_address_for_copy'] is False
    assert set(cleared['facts']) == set(draft()['facts'])  # B facts schema unchanged

@pytest.mark.parametrize('features', ['x'*501, '  ', 'a\x00b', 123])
def test_invalid_features_rejected(setup, features):
    app, client, headers, meta, path, raw = setup
    assert client.put(path.replace('copy-generation', 'input'), headers=headers, json=draft(product_features=features)).status_code == 422

def test_mock_four_copies_dedup_facts_and_original(setup):
    app, client, headers, meta, path, raw = setup
    value = draft(product_features='바삭한 식감')
    save(client, headers, path, value)
    assert client.get(path, headers=headers).json()['status'] == 'pending'
    provider = app.state.copy_store.provider
    calls = []
    real = provider.generate
    provider.generate = lambda payload: (calls.append(payload), real(payload))[1]
    posted = client.post(path, headers=headers, json=request(meta, value))
    assert posted.status_code == 202 and posted.json()['status'] == 'processing'
    assert posted.headers['location'] == path
    response = client.get(path, headers=headers)
    result = response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert result['status'] == 'completed' and result['provider'] == 'mock' and result['is_current']
    assert [v['strategy'] for v in result['variants']] == ['emotional','price','visual','brand']
    assert result['facts'] == value['facts'] and result['product_features'] == value['product_features']
    assert result['expires_at'] == meta['expires_at']
    assert result['attempts'][0]['input_tokens'] is None
    assert 'MOCK_COPY_NOT_LLM' in result['warnings'] and not result['analysis_used']
    assert client.post(path, headers=headers, json=request(meta,value)).json()['status'] == 'completed'
    assert len(calls) == 1
    assert 'address' not in calls[0] and 'instagram_handle' not in calls[0]
    assert client.get('/api/v1/assets/'+meta['asset_id'], headers=headers).content == raw
    assert client.post('/api/v1/jobs', headers=headers).status_code == 404

@pytest.mark.parametrize('field', ['facts','mood','product_features','use_address_for_copy'])
def test_snapshot_conflict_and_stale_results(setup, field):
    app, client, headers, meta, path, raw = setup
    value = draft(product_features='우유 사용', use_address_for_copy=True)
    save(client, headers, path, value)
    client.post(path, headers=headers, json=request(meta,value))
    changed = json.loads(json.dumps(value))
    if field == 'facts': changed['facts']['price_text'] = '10,500원'  # Even spacing is significant.
    elif field == 'mood': changed['mood'] = 'vivid'
    elif field == 'product_features': changed['product_features'] = '우유 미사용'
    else: changed['use_address_for_copy'] = False
    save(client, headers, path, changed)
    old = client.get(path, headers=headers).json()
    assert not old['is_current'] and old['status'] == 'completed'
    owner = app.state.upload_store.authenticate(headers['X-Hanjang-Session'])
    assert app.state.copy_store.current_for_render(owner,meta['job_id']) is None
    assert client.post(path, headers=headers, json=request(meta,value)).status_code == 409
    assert client.post(path, headers=headers, json=request(meta,changed)).status_code == 202
    assert client.get(path, headers=headers).json()['is_current']
    assert len(app.state.upload_store.records[meta['job_id']].copies) == 2

def test_selected_photo_changed_and_stale_analysis_not_sent(setup):
    from app.services.photo_processor import process_photo
    app, client, headers, meta, path, raw = setup
    save(client, headers, path)
    app.state.analysis_store.executor=lambda data:{'clip':{'status':'available','cues':[{'category':'category','candidate_id':'food','label':'음식 추정','similarity':.2}]}}
    client.post(path.replace('copy-generation','photo-analysis'),headers=headers,json={'expected_asset_id':meta['asset_id']})
    requests=[];generate=app.state.copy_store.provider.generate
    app.state.copy_store.provider.generate=lambda payload:(requests.append(payload),generate(payload))[1]
    client.post(path, headers=headers, json=request(meta))
    assert requests[0]['visual_hints'] and client.get(path,headers=headers).json()['analysis_used']
    def mask(im):
        result=Image.new('L',im.size,0);result.paste(255,(50,50,250,250));return result
    app.state.photo_processor=lambda data:process_photo(data,mask)
    processed=client.post(path.replace('copy-generation','photo-processing'),headers=headers)
    photo=client.get(path.replace('copy-generation','photo-processing'),headers=headers).json()
    client.put(path.replace('copy-generation','photo-source'),headers=headers,json={'photo_source':'processed'})
    assert not client.get(path,headers=headers).json()['is_current']
    assert client.post(path,headers=headers,json=request(meta)).status_code==409
    body=request(meta);body['expected_asset_id']=photo['processed']['asset_id']
    assert client.post(path,headers=headers,json=body).status_code==202
    assert requests[-1]['visual_hints']==[]

def test_contact_repeat_in_feature_is_not_sent(setup):
    app,client,headers,meta,path,raw=setup
    save(client,headers,path,draft(product_features='비공개 주소 123 안내'))
    result=client.post(path,headers=headers,json=request(meta,draft(product_features='비공개 주소 123 안내')))
    assert result.status_code==422 and result.json()['error']['code']=='COPY_PRIVATE_INPUT'
    assert not app.state.copy_store.active

def test_ownership_expiry_and_request_validation(setup):
    app, client, headers, meta, path, raw = setup
    assert client.get(path,headers=headers).status_code==409
    save(client,headers,path)
    assert client.get(path).status_code==401
    stranger={'X-Hanjang-Session':client.post('/api/v1/sessions').json()['session_token']}
    assert client.get(path,headers=stranger).status_code==404
    assert client.get('/api/v1/jobs/missing/copy-generation',headers=headers).status_code==404
    assert client.post(path,headers=headers,json={**request(meta),'extra':True}).status_code==422
    assert client.post(path,headers=headers,content=b' '*17000).status_code==413
    client.post(path,headers=headers,json=request(meta))
    app.state.upload_store.records[meta['job_id']].upload.expires_at=now()-timedelta(seconds=1)
    assert client.get(path,headers=headers).status_code==410
    app.state.upload_store.cleanup()
    assert meta['job_id'] not in app.state.upload_store.records

def test_input_change_during_generation_keeps_old_snapshot_stale(setup):
    app,client,headers,meta,path,raw=setup
    save(client,headers,path)
    store=app.state.copy_store;generate=store.provider.generate
    owner=app.state.upload_store.authenticate(headers['X-Hanjang-Session'])
    def changed_while_generating(payload):
        app.state.upload_store.save_draft(owner,meta['job_id'],InputDraft.model_validate(draft(product_features='변경된 특징')))
        return generate(payload)
    store.provider.generate=changed_while_generating
    assert client.post(path,headers=headers,json=request(meta)).status_code==202
    result=client.get(path,headers=headers).json()
    assert result['status']=='completed' and not result['is_current']
    assert result['product_features'] is None and store.current_for_render(owner,meta['job_id']) is None
    assert client.get(path.replace('copy-generation','input'),headers=headers).json()['product_features']=='변경된 특징'

@pytest.mark.parametrize('mode', ['json','duplicate','missing','extra','length','html','control','whitespace','facts','discount','origin','taste','number','price_spacing','same'])
def test_copy_response_rejects_bad_outputs(mode):
    value=InputDraft.model_validate(draft())
    data=json.loads(MockCopyProvider().generate({}).text)
    if mode=='json':raw='{'
    else:
        if mode=='duplicate':data['variants'][1]['strategy']='emotional'
        elif mode=='missing':data['variants'].pop()
        elif mode=='extra':data['variants'][0]['copy']['price_text']='0'
        elif mode=='length':data['variants'][0]['copy']['headline']='가'*61
        elif mode=='html':data['variants'][0]['copy']['headline']='<script>x</script>'
        elif mode=='control':data['variants'][0]['copy']['headline']='a\nb'
        elif mode=='whitespace':data['variants'][0]['copy']['headline']='   '
        elif mode=='facts':data['facts']={'price_text':'0원'}
        elif mode=='discount':data['variants'][0]['copy']['headline']='무료 증정 이벤트'
        elif mode=='origin':data['variants'][0]['copy']['headline']='제주 원산지'
        elif mode=='taste':data['variants'][0]['copy']['headline']='고소한 우유 풍미'
        elif mode=='number':data['variants'][0]['copy']['headline']='500원'
        elif mode=='price_spacing':data['variants'][0]['copy']['headline']='10,500원'
        elif mode=='same':
            for v in data['variants']:v['copy']=data['variants'][0]['copy']
        raw=json.dumps(data)
    with pytest.raises(CopyFailure):validate_copy(raw,value)

def test_supplied_features_and_verbatim_placeholders():
    value=InputDraft.model_validate(draft(product_features='고소한 우유 풍미'))
    data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][0]['copy']['headline']='고소한 우유 풍미'
    data['variants'][1]['copy']['body']='[[price_text]]'
    result=validate_copy(json.dumps(data),value)
    assert result.variants[1].ad_copy.body==value.facts.price_text
    with pytest.raises(CopyFailure):
        long=InputDraft.model_validate({**draft(),'facts':{**draft()['facts'],'store_name':'이'*80}})
        data['variants'][0]['copy']['headline']='[[store_name]]'
        validate_copy(json.dumps(data),long)

def test_provider_payload_privacy_and_analysis_boundary():
    from app.schemas.analysis import Cue
    value=InputDraft.model_validate(draft(product_features='사용자 설명'))
    cues={'visual_hints':[Cue(category='category',candidate_id='drink',label='음료 추정',similarity=.2)]}
    a=provider_payload(value,cues)
    assert set(a)=={'store_name','product_name','price_text','mood','product_features','visual_hints'}
    assert a['store_name']==value.facts.store_name and a['product_features']=='사용자 설명'
    assert value.facts.address not in json.dumps(a,ensure_ascii=False)
    assert value.facts.instagram_handle not in json.dumps(a,ensure_ascii=False)
    value.use_address_for_copy=True
    assert provider_payload(value,None)['address']==value.facts.address
    assert provider_payload(value,None)['visual_hints']==[]

@pytest.mark.parametrize('error,retryable,expected', [('COPY_PROVIDER_TIMEOUT',False,1),('COPY_KEY_MISSING',False,1),('COPY_SCHEMA_INVALID',True,2)])
def test_retry_cap_and_failures_preserve_data(setup,error,retryable,expected):
    app,client,headers,meta,path,raw=setup
    save(client,headers,path)
    calls=[]
    def fail(payload):calls.append(payload);raise CopyFailure(error,retryable)
    app.state.copy_store.provider.generate=fail
    client.post(path,headers=headers,json=request(meta))
    result=client.get(path,headers=headers).json()
    assert result['status']=='failed' and result['error']['code']==error and len(calls)==expected
    assert result['variants']==[] and len(result['attempts'])==expected
    assert client.get('/api/v1/assets/'+meta['asset_id'],headers=headers).content==raw

def test_busy_expiry_during_generation_and_dedup(setup):
    app,client,headers,meta,path,raw=setup
    save(client,headers,path)
    store=app.state.copy_store;owner=app.state.upload_store.authenticate(headers['X-Hanjang-Session'])
    _,task=store.start(owner,meta['job_id'],CopyRequest.model_validate(request(meta)))
    assert task and store.start(owner,meta['job_id'],CopyRequest.model_validate(request(meta)))[1] is None
    other=client.post('/api/v1/uploads',headers=headers,files={'photo':('b.png',raw,'image/png')}).json()
    otherpath=f'/api/v1/jobs/{other["job_id"]}/copy-generation';save(client,headers,otherpath)
    assert client.post(otherpath,headers=headers,json=request(other)).status_code==503
    real=store.provider.generate
    def expire(payload):
        app.state.upload_store.records[meta['job_id']].upload.expires_at=now()-timedelta(seconds=1)
        return real(payload)
    store.provider.generate=expire;store.finish(owner,meta['job_id'],task)
    assert not store.active and client.get(path,headers=headers).status_code==410

def test_budget_persists_six_call_cap_and_unknown_usage(tmp_path):
    path=tmp_path/'usage.json';budget=CopyBudget(path)
    ids=[budget.reserve() for _ in range(6)]
    with pytest.raises(CopyFailure):CopyBudget(path).reserve()
    budget.settle(ids[0],100,100)
    data=json.loads(path.read_text())
    assert data['calls'][0]['usage_known'] and data['calls'][1]['cost_ceiling_usd']==MAX_COST
    assert sum(c['cost_ceiling_usd'] for c in data['calls']) < .1
    assert 'facts' not in path.read_text()

def test_live_gate_never_calls_network(tmp_path):
    class Never:
        def __getattr__(self,name):raise AssertionError('Network forbidden')
    provider=OpenAICopyProvider('gpt-5.4-mini-2026-03-17',None,False,CopyBudget(tmp_path/'ledger'),client=Never())
    with pytest.raises(CopyFailure) as caught:provider.generate({})
    assert caught.value.code=='COPY_PAID_DISABLED' and not (tmp_path/'ledger').exists()

def test_openai_adapter_with_fake_client_only(tmp_path):
    calls=[]
    response=SimpleNamespace(usage=SimpleNamespace(input_tokens=100,output_tokens=200),status='completed',output_text=MockCopyProvider().generate({}).text)
    def create(**kwargs):calls.append(kwargs);return response
    metadata=[]
    client=SimpleNamespace(models=SimpleNamespace(retrieve=lambda model:metadata.append(model)),responses=SimpleNamespace(create=create))
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','test-key-not-real',True,CopyBudget(tmp_path/'ledger'),client)
    payload=provider_payload(InputDraft.model_validate(draft()),None)
    p.generate(payload);p.generate(payload)
    assert len(metadata)==1 and len(calls)==2
    assert calls[0]['store'] is False and calls[0]['max_output_tokens']==2048
    assert calls[0]['reasoning']=={'effort':'none'}
    assert calls[0]['text']['format']['strict']
    assert 'address' not in json.loads(calls[0]['input'][0]['content'])
