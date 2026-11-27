"""Artificial ledgers/fake SDK only; no live calls or real usage history."""
import json
import pytest
from app.services.copy_budget import CopyBudget,MAX_COST
from app.services.copy_contract import CopyFailure
from app.config import Settings


def test_phase4_explicit_cap_does_not_expand_service_or_prior_optins(tmp_path):
    path=tmp_path/'usage.json'
    for kwargs in [{},{'approved_phase3':True},{'approved_quality_experiment':True},{'approved_phase4':'true'}]:
        with pytest.raises(ValueError):CopyBudget(path,19,.1,**kwargs)
    with pytest.raises(ValueError):CopyBudget(path,20,.1,approved_phase4=True)
    with pytest.raises(ValueError):CopyBudget(path,19,.10001,approved_phase4=True)
    assert Settings(_env_file=None).copy_max_requests<=10
    assert Settings(_env_file=None).copy_prompt_profile=='v6'


def test_four_attempts_preserve_fifteen_and_failed_calls_consume_budget(tmp_path):
    path=tmp_path/'usage.json'
    history=[{'id':str(i),'cost_ceiling_usd':.02431050 if i==0 else 0,'state':'completed'} for i in range(15)]
    path.write_text(json.dumps({'calls':history}))
    budget=CopyBudget(path,19,.1,approved_phase4=True)
    assert 4*MAX_COST==pytest.approx(.054864)
    assert .02431050+4*MAX_COST==pytest.approx(.07917450)
    for i in range(4):
        call=budget.reserve();budget.dispatched(call);budget.failed(call,'SYNTHETIC_TEST_FAILURE')
    with pytest.raises(CopyFailure) as e:budget.reserve()
    assert e.value.code=='COPY_BUDGET_EXCEEDED'
    data=json.loads(path.read_text());assert data['calls'][:15]==history and len(data['calls'])==19
    assert all(c['state']=='failed' for c in data['calls'][15:])


@pytest.mark.parametrize('failure',[False,True])
def test_one_use_runner_max_four_stops_on_first_failure(tmp_path,monkeypatch,failure):
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from pydantic import SecretStr
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
    import service_copy_phase4_live as live
    from app.services.copy_provider import MockCopyProvider
    from app.services.copy_prompt import provider_payload
    from app.schemas.upload import InputDraft
    import openai
    monkeypatch.setattr(live,'ROOT',tmp_path);monkeypatch.setattr(live,'OUT',tmp_path/'out')
    monkeypatch.setattr(live,'LEDGER',tmp_path/'synthetic-ledger.json');live.OUT.mkdir()
    history=[{'id':str(i),'cost_ceiling_usd':.02431050 if i==0 else 0} for i in range(15)]
    live.write(live.LEDGER,{'calls':history})
    draft=InputDraft(facts={'store_name':'테스트','product_name':'짜장면','price_text':'7,000원'},mood='warm')
    photo=tmp_path/'synthetic.txt';photo.write_text('not sent as image')
    live.write(live.OUT/'plan.json',{'model':live.MODEL,'instructions':live.INSTRUCTIONS,'prompt_version':live.VERSION,
        'ledger_before':live.ledger_snapshot(),'source_hashes':{},'cases':[{'id':str(i),'photo':photo.name,
            'photo_sha256':live.digest(photo),'draft':draft.model_dump(mode='json'),'goal':'menu_promotion',
            'payload':provider_payload(draft,None,'v8')} for i in range(4)]})
    calls=[]
    def create(**kw):
        calls.append(kw)
        if failure:raise RuntimeError('synthetic failure')
        raw=MockCopyProvider().generate({}).text
        return SimpleNamespace(output_text=raw,status='completed',output=[],usage=SimpleNamespace(input_tokens=100,output_tokens=200),
            model_dump=lambda **kw:{'model':live.MODEL})
    monkeypatch.setattr(openai,'OpenAI',lambda **kw:SimpleNamespace(responses=SimpleNamespace(create=create),close=lambda:None))
    monkeypatch.setattr(live,'Settings',lambda:SimpleNamespace(openai_api_key=SecretStr('synthetic-only'),copy_model=live.MODEL))
    live.execute()
    run=json.loads((live.OUT/'run.json').read_text(encoding='utf-8'))
    assert run['attempts']==len(calls)==(1 if failure else 4)
    assert json.loads(live.LEDGER.read_text())['calls'][:15]==history
    with pytest.raises((AssertionError,FileExistsError)):live.execute()
    assert len(calls)==(1 if failure else 4)
