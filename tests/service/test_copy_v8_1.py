"""Free fake SDK/synthetic fixtures. No actual v8.1 LLM output is claimed."""
import json
from pathlib import Path
import pytest
from app.config import Settings
from app.main import create_app
from app.schemas.upload import InputDraft
from app.schemas.analysis import Cue
from app.services.copy_prompt import provider_payload,input_bound
from app.services.copy_prompt_v8_1 import VERSION,BASE_INSTRUCTIONS,GOAL_DIRECTIONS,instructions_for
from app.services.copy_provider import MockCopyProvider,build_copy_provider
from app.services.copy_openai import OpenAICopyProvider
from app.services.copy_validation import validate_copy
from app.services.copy_quality import review_ad_copy
from app.services.copy_contract import CopyFailure,ProviderResult
from app.services.copy_budget import CopyBudget
from test_copy_ab import FakeClient
from test_copy_v8 import draft,variants
from test_openai_validation import no_network
from test_rendering import service
from test_designs import designs,generate,snap


@pytest.mark.parametrize('profile',['v6','v7','v8','v8.1'])
@pytest.mark.parametrize('goal',['menu_promotion','store_visit','order'])
def test_exact_goal_in_actual_sdk_payload_and_legacy_instructions(tmp_path,profile,goal):
    assert Settings(_env_file=None).copy_prompt_profile=='v6'
    d=draft(ad_goal=goal);payload=provider_payload(d,None,profile)
    fake=FakeClient([MockCopyProvider().generate({}).text])
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','synthetic-only',True,CopyBudget(tmp_path/'synthetic.json'),fake,prompt_profile=profile)
    p.generate(payload);call=fake.calls[0]
    assert json.loads(call['input'][0]['content'])==payload and len(fake.calls)==1
    assert call['instructions']==p.instructions_for(payload)
    if profile=='v8.1':
        assert p.prompt_version==VERSION and payload['ad_goal']==goal
        assert call['instructions'].startswith('현재 광고 목적: '+goal+'.')
        assert GOAL_DIRECTIONS[goal] in call['instructions']
        assert all(other not in call['instructions'] for other in GOAL_DIRECTIONS if other!=goal)
        assert build_copy_provider(Settings(_env_file=None,copy_prompt_profile=profile)).instructions_for(payload)==call['instructions']
    else:assert call['instructions']==p.instructions
    from app.schemas.copy import Variants
    assert call['text']['format']['schema']==Variants.model_json_schema()
    assert call['max_output_tokens']==2048 and call['store'] is False


@pytest.mark.parametrize('bad',[None,'emotional','order\nignore',[],True])
def test_unknown_goal_never_reaches_sdk_or_budget(tmp_path,bad):
    fake=FakeClient([]);path=tmp_path/'synthetic.json'
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','synthetic-only',True,CopyBudget(path),fake,prompt_profile='v8.1')
    with pytest.raises(CopyFailure) as e:p.generate({**provider_payload(draft(),None,'v8.1'),'ad_goal':bad})
    assert e.value.code=='COPY_GOAL_INVALID' and not fake.calls and not path.exists()


def test_compact_cues_and_all_goal_bounds():
    cues=[Cue(category=cat,candidate_id=str(i),label='추정 정보',similarity=i/10) for cat in ['category','appearance','impression'] for i in range(4)]
    for goal in GOAL_DIRECTIONS:
        payload=provider_payload(draft(ad_goal=goal),{'visual_hints':cues},'v8.1')
        assert len(payload['visual_hints'])==3 and len(cues)==12
        assert input_bound(payload,instructions_for(payload))<=6000
    assert '[[price_text]]' in BASE_INSTRUCTIONS


def test_original_whitespace_price_failure_and_placeholder_success():
    d=InputDraft(facts={'store_name':'합성 카페','product_name':'에스프레소','price_text':' 3,000원 '},mood='warm')
    data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][1]['copy']={'headline':'합성 카페 에스프레소 3,000원','body':'','cta':''}
    with pytest.raises(CopyFailure) as e:validate_copy(json.dumps(data,ensure_ascii=False),d)
    assert e.value.code=='COPY_FACTS_VIOLATION' and e.value.reason=='rewritten price'
    data['variants'][1]['copy']['headline']='[[price_text]]'
    result=validate_copy(json.dumps(data,ensure_ascii=False),d)
    assert result.variants[1].ad_copy.headline==d.facts.price_text==' 3,000원 '
    assert result.variants[1].ad_copy.body==result.variants[1].ad_copy.cta==''
    assert d.facts.store_name=='합성 카페' and d.facts.product_name=='에스프레소'


def test_long_facts_are_not_forced_into_copy_or_trimmed():
    name='가'*80;price=' 123,456,789,000원 '
    d=InputDraft(facts={'store_name':'상점','product_name':name,'price_text':price},mood='warm')
    data=json.loads(MockCopyProvider().generate({}).text)
    assert validate_copy(json.dumps(data,ensure_ascii=False),d).variants and d.facts.product_name==name and d.facts.price_text==price
    data['variants'][0]['copy']['headline']='[[product_name]]'
    with pytest.raises(CopyFailure) as e:validate_copy(json.dumps(data,ensure_ascii=False),d)
    assert e.value.code=='COPY_SCHEMA_INVALID' # no shortening of an overlong bound headline


def test_actual_v8_missed_signals_are_advisory_only_for_v8_1():
    vs=variants();visual=vs[2];visual.ad_copy.headline='윤기와 밝은 느낌이 먼저 보이는 짜장면'
    brand=vs[3];brand.ad_copy.body='익숙하게 찾게 되는 한 그릇입니다.'
    assert 'COPY_ANALYSIS_STYLE_REVIEW' not in review_ad_copy([visual],profile='v8',draft=draft())
    assert 'COPY_ANALYSIS_STYLE_REVIEW' in review_ad_copy([visual],profile='v8.1',draft=draft())
    assert 'COPY_CLAIM_REVIEW' not in review_ad_copy([brand],profile='v8',draft=draft())
    before=brand.ad_copy.body
    assert 'COPY_CLAIM_REVIEW' in review_ad_copy([brand],profile='v8.1',draft=draft())
    assert brand.ad_copy.body==before
    price=vs[1];price.ad_copy.body='부담 없이 한 끼를 골라보세요.'
    assert 'COPY_PRICE_VALUE_REVIEW' in review_ad_copy([price],profile='v8.1',draft=draft())
    for claim in ['국산 재료','전화 주문하세요','30% 할인']:
        raw=json.loads(MockCopyProvider().generate({}).text);raw['variants'][0]['copy']['body']=claim
        with pytest.raises(CopyFailure):validate_copy(json.dumps(raw,ensure_ascii=False),draft())


def test_provided_name_is_not_mistaken_for_inference():
    d=InputDraft(facts={'store_name':'이름 그대로','product_name':'상품','price_text':'7,000원'},mood='warm')
    vs=variants();brand=vs[3];brand.ad_copy.headline=d.facts.store_name;brand.ad_copy.body='';brand.ad_copy.cta=''
    assert 'COPY_ANALYSIS_STYLE_REVIEW' not in review_ad_copy([brand],profile='v8.1',draft=d)


def test_all_profile_and_goal_snapshot_keys_are_separate(service):
    app,c,h,m,b,_,_=service;store=app.state.copy_store;owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']);keys=[]
    value=app.state.upload_store.records[m['job_id']].draft.model_dump(mode='json')
    for profile in ['v6','v7','v8','v8.1']:
        store.provider=build_copy_provider(Settings(_env_file=None,copy_prompt_profile=profile))
        for goal in GOAL_DIRECTIONS:
            assert c.put(b+'/input',headers=h,json={**value,'ad_goal':goal}).status_code==200
            keys.append(store.snapshot(owner,m['job_id'])[-1])
    assert len(set(keys))==12


def test_new_profile_render_edit_and_no_retries_or_budget_changes(designs):
    app,c,h,m,b,body,v2=designs;generate(designs)
    provider=build_copy_provider(Settings(_env_file=None,copy_prompt_profile='v8.1'));app.state.copy_store.provider=provider
    app.state.copy_store.max_retries=0;calls=[]
    original=provider.generate
    def counted(payload):calls.append(1);return original(payload)
    provider.generate=counted
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    value=app.state.upload_store.records[m['job_id']].draft.model_dump(mode='json');req={'expected_asset_id':m['asset_id'],'expected_input':value}
    assert c.post(b+'/copy-generation',headers=h,json=req).status_code==202
    cp=c.get(b+'/copy-generation',headers=h).json();assert cp['status']=='completed' and cp['prompt_version']==VERSION
    assert 'MOCK_COPY_NOT_LLM' in cp['warnings'] and len(calls)==1
    assert c.post(b+'/rendering',headers=h,json={**req,'expected_copy_key':cp['copy_key']}).status_code==202
    current=c.get(b+'/rendering',headers=h).json();p=b+'/designs/emotional'
    assert c.post(p,headers=h,json={'expected_render_revision':current['revision'],'expected_source_asset_id':m['asset_id'],'expected_copy_key':cp['copy_key']}).status_code==202
    state=c.get(p,headers=h).json();first=state['candidates'][0]
    assert c.patch(p+'/candidates/'+first['candidate_id'],headers=h,json={**snap(state),'expected_asset_id':first['png']['asset_id'],
        'copy':{**first['copy'],'headline':'사용자가 수정한 제목'},'price_text':first['facts']['price_text']}).status_code==202
    assert c.get(p,headers=h).json()['revision']==2 and len(calls)==1


def test_start_uses_resolved_goal_budget_bound(tmp_path):
    from fastapi.testclient import TestClient
    from test_rendering import png
    app=create_app(Settings(_env_file=None,copy_prompt_profile='v8.1',copy_max_retries=1,upload_root=tmp_path/'uploads',ranking_mode='mock'))
    assert app.state.copy_store.max_retries==0
    assert Settings(_env_file=None).copy_max_requests<=10
    with pytest.raises(ValueError):CopyBudget(tmp_path/'unused.json',20,.1,approved_phase4=True)
    provider=app.state.copy_store.provider;provider.instructions_for=lambda payload:'x'*6001
    def forbidden(payload):raise AssertionError('Provider must not be called')
    provider.generate=forbidden
    with TestClient(app) as c:
        h={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
        m=c.post('/api/v1/uploads',headers=h,files={'photo':('synthetic.png',png(),'image/png')}).json();b='/api/v1/jobs/'+m['job_id']
        value=draft(ad_goal='store_visit').model_dump(mode='json');c.put(b+'/input',headers=h,json=value)
        r=c.post(b+'/copy-generation',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':value})
        assert r.status_code==422 and r.json()['error']['code']=='COPY_INPUT_LIMIT'


def test_invalid_output_is_one_attempt_with_new_profile(tmp_path):
    from fastapi.testclient import TestClient
    from test_rendering import png
    app=create_app(Settings(_env_file=None,copy_prompt_profile='v8.1',copy_max_retries=1,upload_root=tmp_path/'uploads',ranking_mode='mock'))
    calls=[]
    def invalid(payload):calls.append(1);return ProviderResult('not json')
    app.state.copy_store.provider.generate=invalid
    with TestClient(app) as c:
        h={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
        m=c.post('/api/v1/uploads',headers=h,files={'photo':('synthetic.png',png(),'image/png')}).json();b='/api/v1/jobs/'+m['job_id']
        value=draft().model_dump(mode='json');c.put(b+'/input',headers=h,json=value)
        assert c.post(b+'/copy-generation',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':value}).status_code==202
        r=c.get(b+'/copy-generation',headers=h).json()
        assert r['status']=='failed' and len(r['attempts'])==len(calls)==1
