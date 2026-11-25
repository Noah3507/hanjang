import json
import pytest
from app.schemas.upload import InputDraft
from app.services.copy_budget import CopyBudget
from app.services.copy_contract import CopyFailure
from app.services.copy_prompt import SYSTEM_PROMPT,provider_payload
from app.services.copy_prompt_v7 import INSTRUCTIONS
from app.services.copy_openai import OpenAICopyProvider
from app.services.copy_provider import MockCopyProvider
from app.services.copy_quality import review_ad_copy
from app.services.copy_validation import validate_copy
from test_rendering import service
from test_designs import designs,generate,snap
from test_copy_ab import FakeClient

def test_goal_default_save_omission_and_changed_cache_fence(designs):
    app,c,h,m,b,_,_=designs;p,s=generate(designs);c.post(p+'/ranking',headers=h,json=snap(s))
    initial=c.get(b+'/input',headers=h).json();assert initial['ad_goal']=='menu_promotion'
    value={k:initial[k] for k in ['facts','mood','product_features','use_address_for_copy']}
    assert c.put(b+'/input',headers=h,json={**value,'ad_goal':'store_visit'}).status_code==200
    assert c.put(b+'/input',headers=h,json=value).status_code==200
    assert c.get(b+'/input',headers=h).json()['ad_goal']=='store_visit'
    assert not c.get(b+'/copy-generation',headers=h).json()['is_current']
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    stale=c.get(p,headers=h).json();assert not stale['is_current'] and stale['ranking'] is None
    for invalid in [None,'emotional','visit']:
        assert c.put(b+'/input',headers=h,json={**value,'ad_goal':invalid}).status_code==422
    expected={**value,'ad_goal':'store_visit'}
    assert c.post(b+'/copy-generation',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':expected}).status_code==202
    new=c.get(b+'/copy-generation',headers=h).json()
    assert new['status']=='completed' and new['ad_goal']=='store_visit' and new['is_current']

def test_opt_in_prompt_instance_and_no_global_mutation(tmp_path):
    from app.config import Settings
    from app.main import create_app
    app=create_app(Settings(_env_file=None,upload_root=tmp_path/'uploads',copy_prompt_profile='v7',copy_max_retries=1,ranking_mode='mock'))
    assert app.state.copy_store.max_retries==0
    client=FakeClient([MockCopyProvider().generate({}).text])
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','synthetic-test-only',True,CopyBudget(tmp_path/'ledger.json'),client,prompt_profile='v7')
    draft=InputDraft(facts={'store_name':'가게','product_name':'짜장면','price_text':'7,000원'},mood='warm',ad_goal='order')
    reply=p.generate(provider_payload(draft,None,'v7'))
    assert client.calls[0]['instructions']==INSTRUCTIONS and client.calls[0]['instructions']!=SYSTEM_PROMPT
    assert json.loads(client.calls[0]['input'][0]['content'])['ad_goal']=='order'
    assert validate_copy(reply.text,draft).variants
    from app.services.copy_prompt import SYSTEM_PROMPT as unchanged
    assert unchanged==SYSTEM_PROMPT

def test_experiment_budget_fifteen_only_opt_in_and_history_preserved(tmp_path):
    path=tmp_path/'ledger.json';history=[{'id':str(i),'cost_ceiling_usd':.01952175 if i==0 else 0} for i in range(12)]
    path.write_text(json.dumps({'calls':history}))
    with pytest.raises(ValueError):CopyBudget(path,15,.1)
    with pytest.raises(ValueError):CopyBudget(path,16,.1,approved_quality_experiment=True)
    budget=CopyBudget(path,15,.1,approved_quality_experiment=True)
    for _ in range(3):budget.reserve()
    with pytest.raises(CopyFailure):budget.reserve()
    assert json.loads(path.read_text())['calls'][:12]==history

def test_service_cta_warning_is_not_a_paid_retry_or_rewrite():
    draft=InputDraft(facts={'store_name':'가게','product_name':'짜장면','price_text':'7,000원'},mood='warm')
    data=json.loads(MockCopyProvider().generate({}).text);data['variants'][0]['copy']['cta']='사진으로 확인해 보세요'
    result=validate_copy(json.dumps(data,ensure_ascii=False),draft)
    assert 'COPY_SERVICE_LANGUAGE_REVIEW' in review_ad_copy(result.variants)
    assert result.variants[0].ad_copy.cta=='사진으로 확인해 보세요'

def test_empty_body_cta_and_unprovided_order_routes():
    draft=InputDraft(facts={'store_name':'가게','product_name':'짜장면','price_text':'7,000원'},mood='warm',ad_goal='order')
    data=json.loads(MockCopyProvider().generate({}).text)
    data['variants'][1]['copy']={'headline':'[[product_name]] [[price_text]]','body':'','cta':''}
    assert validate_copy(json.dumps(data,ensure_ascii=False),draft).variants[1].ad_copy.cta==''
    for route in ['전화로 주문하세요','배달로 즐겨보세요','온라인 주문하세요']:
        data['variants'][1]['copy']['cta']=route
        with pytest.raises(CopyFailure):validate_copy(json.dumps(data,ensure_ascii=False),draft)
