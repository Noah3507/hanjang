import json
import shutil
from pathlib import Path
import pytest
from app.services.copy_template_limits import load_template_limits,review_bound_lengths
from app.services.copy_prompt import provider_payload
from app.services.copy_campaign import instructions_for
from app.services.copy_budget import CopyBudget
from app.services.copy_contract import CopyFailure
from app.services.copy_provider import MockCopyProvider
from app.schemas.copy import Variants
from test_copy_v8 import draft
from test_rendering import service
from test_designs import designs,generate,snap


def test_measured_contract_is_in_campaign_only():
    limits=load_template_limits()
    price=dict(limits['strategies']['price']['headline'])
    assert 0<price['soft']<=price['hard']
    # Template changes re-measure limits.json (B); the numbers themselves are checked in test_template_limits.py.
    emotional=limits['strategies']['emotional']['headline']
    assert 0<emotional['soft']<=emotional['hard']
    assert 'template_copy_limits' not in provider_payload(draft(),None,'v6')
    payload=provider_payload(draft(),None,'campaign')
    assert payload['template_copy_limits']==limits and '치환 후 공백까지' in instructions_for(payload)
    payload['template_copy_limits']['strategies']['price']['headline']['soft']=1
    assert load_template_limits()['strategies']['price']['headline']==price


def test_stale_missing_and_invalid_contract_never_invent_limits(tmp_path):
    assert load_template_limits(tmp_path) is None
    root=Path(__file__).resolve().parents[2]
    folder=tmp_path/'templates/v3';folder.mkdir(parents=True)
    for file in (root/'templates/v3').iterdir():
        if file.suffix in ('.html','.css','.json'):shutil.copyfile(file,folder/file.name)
    assert load_template_limits(tmp_path) is not None
    path=folder/'quality.css';path.write_text(path.read_text(encoding='utf-8')+'\n/* stale test */',encoding='utf-8')
    assert load_template_limits(tmp_path) is None


def test_lengths_use_bound_facts_and_spaces_and_remain_advisory():
    limits=load_template_limits()
    raw=json.loads(MockCopyProvider().generate({}).text)
    measured=limits['strategies'][raw['variants'][0]['strategy']]['headline']
    assert measured['soft']<measured['hard'], 'needs a strategy whose headline can shrink'
    raw['variants'][0]['copy']['headline']='가'*measured['soft']
    values=Variants.model_validate(raw).variants
    assert review_bound_lengths(values,limits)==[]
    raw['variants'][0]['copy']['headline']='가'*(measured['soft']+1)
    values=Variants.model_validate(raw).variants
    assert 'COPY_TEMPLATE_SOFT_LIMIT_REVIEW' in review_bound_lengths(values,limits)
    raw['variants'][0]['copy']['headline']='가'*(measured['hard']+1)
    values=Variants.model_validate(raw).variants
    before=values[0].ad_copy.headline
    assert 'COPY_TEMPLATE_HARD_LIMIT_REVIEW' in review_bound_lengths(values,limits)
    assert values[0].ad_copy.headline==before


def test_continuous_local_rename_failure_keeps_history(tmp_path,monkeypatch):
    import app.services.copy_budget as module
    path=tmp_path/'usage.json';before='{"calls":[]}'
    path.write_text(before);attempts=[]
    def fail(*args):
        attempts.append(1);error=PermissionError('synthetic');error.winerror=32;raise error
    monkeypatch.setattr(module,'_WINDOWS',True)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    monkeypatch.setattr(Path,'replace',fail)
    with pytest.raises(CopyFailure,match='COPY_BUDGET_UNAVAILABLE'):CopyBudget(path).reserve()
    assert len(attempts)==5 and path.read_text()==before


def test_template_source_change_stales_v3_without_copy_regeneration(designs,monkeypatch):
    app,c,h,m,b,body,v2=designs
    path,state=generate(designs)
    assert c.post(path+'/ranking',headers=h,json=snap(state)).status_code==200
    copy_before=c.get(b+'/copy-generation',headers=h).json()
    def forbidden(*args):pytest.fail('Template change must reuse copy, never call LLM')
    monkeypatch.setattr(app.state.copy_store.provider,'generate',forbidden)
    monkeypatch.setattr('app.services.design_store.template_fingerprint',lambda:'new-html-css-source')
    latest=c.get(path,headers=h).json()
    assert not latest['is_current'] and latest['ranking'] is None
    first=state['candidates'][0]
    assert c.get(path+'/candidates/'+first['candidate_id']+'/download',headers=h,params={'format':'png',**snap(state)}).status_code==409
    assert c.post(path,headers=h,json=body).status_code==202
    assert c.get(path,headers=h).json()['is_current']
    assert c.get(b+'/copy-generation',headers=h).json()['copy_key']==copy_before['copy_key']
    assert c.get(b+'/rendering',headers=h).json()==v2


def test_v6_can_use_explicit_operator_policy_without_experiment_budget(tmp_path):
    from app.config import Settings
    from app.services.copy_provider import build_copy_provider
    settings=Settings(_env_file=None,copy_provider='openai',copy_usage_policy='service',copy_max_requests=128,copy_budget_usd=2,copy_budget_path=tmp_path/'usage.json')
    provider=build_copy_provider(settings)
    assert provider.prompt_profile=='v6' and provider.budget.max_requests==128
    assert provider.budget.budget_usd==2 and not provider.allow_paid
