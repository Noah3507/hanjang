"""Synthetic fixtures/fake SDK only. These are NOT actual v8 LLM outputs."""
import json
from types import SimpleNamespace
import pytest
from app.config import Settings
from app.main import create_app
from app.schemas.upload import InputDraft
from app.schemas.analysis import Cue
from app.services.copy_prompt import SYSTEM_PROMPT,provider_payload,input_bound
from app.services.copy_prompt_v8 import INSTRUCTIONS,VERSION
from app.services.copy_provider import MockCopyProvider,build_copy_provider
from app.services.copy_openai import OpenAICopyProvider
from app.services.copy_budget import CopyBudget,MAX_COST
from app.services.copy_contract import CopyFailure,ProviderResult
from app.services.copy_quality import review_ad_copy
from app.services.copy_validation import validate_copy
from test_copy_ab import FakeClient
from test_openai_validation import no_network
from test_rendering import service
from test_designs import designs,generate,snap


def draft(**kw):
    return InputDraft(facts={'store_name':'테스트 가게','product_name':'짜장면','price_text':' 7,000원 '},mood='warm',**kw)


def variants(**changes):
    data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][0]['copy'].update(changes)
    return validate_copy(json.dumps(data,ensure_ascii=False),draft()).variants


@pytest.mark.parametrize('profile', ['v6','v7','v8'])
def test_profile_adapter_wire_contract_and_default(tmp_path,profile):
    assert Settings(_env_file=None).copy_prompt_profile=='v6'
    settings=Settings(_env_file=None,copy_prompt_profile=profile)
    mock=build_copy_provider(settings)
    app=create_app(Settings(_env_file=None,copy_prompt_profile=profile,copy_max_retries=1,upload_root=tmp_path/'uploads',ranking_mode='mock'))
    assert app.state.copy_store.max_retries==(1 if profile=='v6' else 0)
    fake=FakeClient([MockCopyProvider().generate({}).text])
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','fake-not-a-key',True,CopyBudget(tmp_path/'ledger.json'),fake,prompt_profile=profile)
    payload=provider_payload(draft(),None,profile);p.generate(payload)
    call=fake.calls[0]
    assert call['instructions']==p.instructions and call['max_output_tokens']==2048 and call['store'] is False
    assert len(fake.calls)==1 and call['reasoning']=={'effort':'none'}
    if profile=='v8':assert p.instructions==INSTRUCTIONS and p.prompt_version==VERSION==mock.prompt_version and mock.instructions==INSTRUCTIONS
    elif profile=='v6':assert p.instructions==SYSTEM_PROMPT and 'ad_goal' not in payload
    else:assert p.prompt_version=='copy-v7-purpose-concise'
    assert validate_copy(MockCopyProvider().generate({}).text,draft()).variants


@pytest.mark.parametrize('goal',['menu_promotion','store_visit','order'])
def test_explicit_goal_three_cues_privacy_and_bound(goal):
    cues=[Cue(category=cat,candidate_id=str(i),label='시각 추정',similarity=.1+i*.1)
          for cat in ['category','appearance','impression'] for i in range(4)]
    context={'visual_hints':cues};payload=provider_payload(draft(ad_goal=goal),context,'v8')
    assert payload['ad_goal']==goal and len(payload['visual_hints'])==3 and len(context['visual_hints'])==12
    assert [c['category'] for c in payload['visual_hints']]==['category','appearance','impression']
    assert all(c['candidate_id']=='3' for c in payload['visual_hints'])
    assert input_bound(payload,INSTRUCTIONS)<=6000 and 'address' not in payload and 'photo' not in payload


def test_fact_placeholders_empty_copy_and_safety_unchanged():
    data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][1]['copy']={'headline':'[[product_name]] [[price_text]]','body':'','cta':''}
    raw=json.dumps(data,ensure_ascii=False);result=validate_copy(raw,draft())
    assert result.variants[1].ad_copy.headline=='짜장면  7,000원 ' and result.variants[1].ad_copy.body==result.variants[1].ad_copy.cta==''
    for claim in ['수제 짜장면','국산 재료','전화로 주문하세요','30% 할인','가격 6,500원']:
        data['variants'][1]['copy']['body']=claim
        with pytest.raises(CopyFailure):validate_copy(json.dumps(data,ensure_ascii=False),draft())


@pytest.mark.parametrize('goal,cta,warning',[
 ('menu_promotion','주문해 보세요',True),('menu_promotion','매장에 들러보세요',True),
 ('menu_promotion','오늘 메뉴로 골라보세요',False),('menu_promotion','주문 전에 메뉴를 살펴보세요',False),
 ('store_visit','주문하세요',True),('store_visit','메뉴를 살펴보세요',True),('store_visit','매장에 들러보세요',False),
 ('order','메뉴를 골라보세요',True),('order','매장에 들러보세요',True),('order','한 그릇 주문해 보세요',False),
 ('order','',False),('store_visit','',False)])
def test_cta_semantic_cues_advisory_only(goal,cta,warning):
    vs=variants(cta=cta)
    ws=review_ad_copy([vs[0]],goal,profile='v8',draft=draft())
    assert ('COPY_GOAL_REVIEW' in ws)==warning
    assert vs[0].ad_copy.cta==cta


@pytest.mark.parametrize('changes,warning',[
 ({'body':'사진 속 표면이 매끈하게 보입니다.'},'COPY_ANALYSIS_STYLE_REVIEW'),
 ({'body':'가게 이름으로 메뉴를 고를 때 떠오르는 한 그릇입니다.'},'COPY_ANALYSIS_STYLE_REVIEW'),
 ({'body':'장인의 정통 한 그릇'},'COPY_CLAIM_REVIEW'),
 ({'cta':'먹어볼까'},'COPY_CTA_STYLE_REVIEW'),
 ({'headline':'[[product_name]]','body':'[[product_name]]'},'COPY_FACT_REPETITION_REVIEW'),
 ({'body':'오늘 메뉴를 고르는 시간에 이 한 그릇을 떠올리며 천천히 둘러보고 마음에 드는 메뉴를 직접 선택해 보세요.'},'COPY_LENGTH_REVIEW')])
def test_quality_warnings_do_not_reject_rewrite_or_certify(changes,warning):
    vs=variants(**changes);before=[v.model_dump(mode='json',by_alias=True) for v in vs]
    assert warning in review_ad_copy(vs,profile='v8',draft=draft())
    assert [v.model_dump(mode='json',by_alias=True) for v in vs]==before


def test_natural_prose_supplied_claims_long_facts_and_cross_strategy():
    d=InputDraft(facts={'store_name':'테스트 가게','product_name':'아주 긴 상품 이름 '*5,'price_text':'7,000원'},mood='warm',product_features='장인의 정통 방식')
    # Direct advisory input, not an actual LLM result or a bypass of the service validator.
    v=SimpleNamespace(ad_copy=SimpleNamespace(headline=d.facts.product_name,body='장인의 정통 방식',cta='',model_dump=lambda:{'headline':d.facts.product_name,'body':'장인의 정통 방식','cta':''}))
    assert review_ad_copy([v],profile='v8',draft=d)==[]
    vs=variants();vs[1].ad_copy.headline=vs[0].ad_copy.headline
    assert 'COPY_REPETITION_REVIEW' in review_ad_copy(vs,profile='v8',draft=draft())


def test_profile_cache_fences_existing_render_and_warnings_never_retry(designs):
    app,c,h,m,b,body,v2=designs;p,old=generate(designs)
    app.state.copy_store.provider=build_copy_provider(Settings(_env_file=None,copy_prompt_profile='v8'))
    app.state.copy_store.max_retries=0
    assert not c.get(b+'/copy-generation',headers=h).json()['is_current']
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    assert not c.get(p,headers=h).json()['is_current']
    provider=app.state.copy_store.provider;original=provider.generate;calls=[]
    def counted(payload):calls.append(1);return original(payload)
    provider.generate=counted
    expected=app.state.upload_store.records[m['job_id']].draft.model_dump(mode='json')
    render_body={'expected_asset_id':m['asset_id'],'expected_input':expected}
    assert c.post(b+'/copy-generation',headers=h,json=render_body).status_code==202
    cp=c.get(b+'/copy-generation',headers=h).json()
    assert cp['status']=='completed' and cp['prompt_version']==VERSION and len(calls)==1
    assert 'MOCK_COPY_NOT_LLM' in cp['warnings'] and 'COPY_SERVICE_LANGUAGE_REVIEW' in cp['warnings']
    assert c.post(b+'/rendering',headers=h,json={**render_body,'expected_copy_key':cp['copy_key']}).status_code==202
    current=c.get(b+'/rendering',headers=h).json();assert current['status']=='completed'
    from test_editor import target
    first=current['candidates'][0]
    assert c.patch(target(b,current),headers=h,json={**render_body,'expected_copy_key':cp['copy_key'],
        'expected_revision':current['revision'],'expected_candidate_ids':[v['candidate_id'] for v in current['candidates']],
        'copy':{**first['copy'],'headline':'새로운 제목'}}).status_code==202
    assert len(calls)==1


def test_paid_gate_and_existing_fifteen_cap_unchanged(tmp_path):
    fake=FakeClient([]);path=tmp_path/'ledger.json'
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','fake',False,CopyBudget(path),fake,prompt_profile='v8')
    with pytest.raises(CopyFailure) as e:p.generate(provider_payload(draft(),None,'v8'))
    assert e.value.code=='COPY_PAID_DISABLED' and not path.exists() and not fake.calls
    history={'calls':[{'id':str(i),'cost_ceiling_usd':0} for i in range(15)]};path.write_text(json.dumps(history))
    budget=CopyBudget(path,15,.1,approved_quality_experiment=True)
    with pytest.raises(CopyFailure) as e:budget.reserve()
    assert e.value.code=='COPY_BUDGET_EXCEEDED' and json.loads(path.read_text())==history
    with pytest.raises(ValueError):CopyBudget(path,16,.1,approved_quality_experiment=True)
    assert MAX_COST==pytest.approx(.013716)


def test_three_profile_snapshot_keys_separate_with_same_facts(service):
    app,c,h,m,b,_,_=service;store=app.state.copy_store
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);keys=[]
    for profile in ['v6','v7','v8']:
        store.provider=build_copy_provider(Settings(_env_file=None,copy_prompt_profile=profile))
        keys.append(store.snapshot(owner,m['job_id'])[-1])
    assert len(set(keys))==3


@pytest.mark.parametrize('bad',['invalid-json','unprovided-claim'])
def test_v8_invalid_output_never_retries(tmp_path,bad):
    from fastapi.testclient import TestClient
    from test_rendering import png
    app=create_app(Settings(_env_file=None,upload_root=tmp_path/'uploads',copy_prompt_profile='v8',copy_max_retries=1,ranking_mode='mock'))
    calls=[];data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][0]['copy']['body']='국산 수제 상품'
    def invalid(payload):calls.append(1);return ProviderResult('not json' if bad=='invalid-json' else json.dumps(data,ensure_ascii=False))
    app.state.copy_store.provider.generate=invalid
    with TestClient(app) as c:
        h={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
        m=c.post('/api/v1/uploads',headers=h,files={'photo':('synthetic.png',png(),'image/png')}).json()
        b='/api/v1/jobs/'+m['job_id'];value=draft().model_dump(mode='json')
        assert c.put(b+'/input',headers=h,json=value).status_code==200
        assert c.post(b+'/copy-generation',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':value}).status_code==202
        result=c.get(b+'/copy-generation',headers=h).json()
        assert result['status']=='failed' and len(result['attempts'])==1 and len(calls)==1
