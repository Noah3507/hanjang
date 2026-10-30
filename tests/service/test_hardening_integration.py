"""Offline integration regression: retain results/ranking while hardening copy."""
import json
from pathlib import Path
import pytest
from app.services.copy_budget import CopyBudget
from app.services.copy_contract import CopyFailure
from app.services.copy_prompt import input_bound, provider_payload
from app.services.render_execution import RenderExecution, RenderFailure
from app.schemas.upload import InputDraft
from test_rendering import service, draft, png
from test_ranking import rendered
from test_openai_validation import provider, reply


@pytest.mark.parametrize('content', ['{bad', '[]', '{"calls":{}}', '{"calls":[{"id":"x","cost_ceiling_usd":true}]}'])
def test_invalid_ledger_preserved(tmp_path, content):
    path = tmp_path/'ledger.json'; path.write_text(content)
    with pytest.raises(CopyFailure, match='COPY_BUDGET_INVALID'):
        CopyBudget(path).reserve()
    assert path.read_text() == content


def test_ledger_io_failure_blocks_dispatch(tmp_path, monkeypatch):
    p, calls, budget = provider(tmp_path, lambda _: reply())
    original = Path.replace
    def fail(path, other):
        if path == budget.path.with_suffix('.tmp'):
            raise PermissionError('private-path-do-not-expose')
        return original(path, other)
    monkeypatch.setattr(Path, 'replace', fail)
    with pytest.raises(CopyFailure, match='COPY_BUDGET_UNAVAILABLE'):
        p.generate({})
    assert calls == [] and not budget.path.exists()


def test_failure_record_does_not_mask_original(tmp_path, monkeypatch):
    p, calls, budget = provider(tmp_path, lambda _: reply(status='incomplete'))
    def fail(*args): raise PermissionError('private marker')
    monkeypatch.setattr(budget, 'failed', fail)
    with pytest.raises(CopyFailure) as caught: p.generate({})
    assert caught.value.code == 'COPY_OUTPUT_INCOMPLETE' and len(calls) == 1
    assert 'private marker' not in str(caught.value)
    assert json.loads(budget.path.read_text())['calls']


@pytest.mark.parametrize('missing', [False, True])
def test_font_missing_or_corrupt_keeps_specific_error(tmp_path, monkeypatch, missing):
    import app.services.render_execution as execution
    font = tmp_path/'templates/fonts/NotoSansKR-Regular.otf'
    font.parent.mkdir(parents=True)
    if not missing: font.write_bytes(b'corrupt')
    monkeypatch.setattr(execution, 'ROOT', tmp_path)
    with pytest.raises(RenderFailure) as caught:
        RenderExecution()(InputDraft.model_validate(draft()), None, png())
    assert caught.value.code == 'RENDER_FONT_UNAVAILABLE'


@pytest.mark.parametrize('policy', ['PROMPT_VERSION', 'POLICY_VERSION'])
def test_policy_change_stales_all_and_regenerates(service, monkeypatch, policy):
    import app.services.copy_store as copy_module
    app,c,h,m,b,request,old_render = rendered(service)
    c.post(b+'/ranking', headers=h, json=request)
    old_rank = c.get(b+'/ranking', headers=h).json()
    monkeypatch.setattr(copy_module, policy, 'future-policy-for-test')
    assert not c.get(b+'/copy-generation',headers=h).json()['is_current']
    assert not c.get(b+'/rendering',headers=h).json()['is_current']
    assert not c.get(b+'/ranking',headers=h).json()['is_current']
    assert c.post(b+'/ranking',headers=h,json=request).status_code == 409
    cb = {'expected_asset_id':m['asset_id'],'expected_input':draft()}
    assert c.post(b+'/copy-generation',headers=h,json=cb).status_code == 202
    copy = c.get(b+'/copy-generation',headers=h).json()
    assert copy['is_current']
    assert c.post(b+'/rendering',headers=h,json={**cb,'expected_copy_key':copy['copy_key']}).status_code == 202
    render = c.get(b+'/rendering',headers=h).json()
    assert render['is_current'] and render['revision'] > old_render['revision']
    req = {'expected_render_revision':render['revision'],'expected_candidate_ids':[x['candidate_id'] for x in render['candidates']]}
    assert c.post(b+'/ranking',headers=h,json=req).status_code == 202
    ranking = c.get(b+'/ranking',headers=h).json()
    assert ranking['is_current'] and ranking['ranking'] != old_rank['ranking']
    assert c.get('/api/v1/assets/'+m['asset_id'],headers=h).content == service[-1]


def test_prompt_limit_rejects_without_truncation_or_dispatch(service):
    app,c,h,m,b,_,_ = service
    d = draft(); d['facts']['store_name']='가'*80; d['facts']['product_name']='나'*80
    d['facts']['price_text']='값'*40; d['facts']['address']='집'*200; d['use_address_for_copy']=True
    d['product_features']='특'*500
    payload=provider_payload(InputDraft.model_validate(d),None)
    assert input_bound(payload) > 6000
    assert c.put(b+'/input',headers=h,json=d).status_code == 200
    response=c.post(b+'/copy-generation',headers=h,json={'expected_asset_id':m['asset_id'],'expected_input':d})
    assert response.status_code==422 and response.json()['error']['code']=='COPY_INPUT_LIMIT'
    assert c.get(b+'/input',headers=h).json()['product_features']==d['product_features']
