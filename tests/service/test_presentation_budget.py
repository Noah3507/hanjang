"""Budget expansion uses synthetic ledgers and fake SDK only."""
import json
import pytest
from app.config import Settings
from app.services.copy_budget import CopyBudget, MAX_COST
from app.services.copy_contract import CopyFailure
from test_copy import setup, save, request
from test_openai_validation import no_network, provider, reply


def historical_ledger(tmp_path):
    costs=[.001599,.001374,.00156075,.001485,.001557,.0014865]
    records=[{'id':f'synthetic-history-{i}','cost_ceiling_usd':cost,'usage_known':True,'state':'completed'}
        for i,cost in enumerate(costs)]
    path=tmp_path/'ledger.json';path.write_text(json.dumps({'calls':records}))
    return path,records


def test_explicit_expansion_preserves_six_records_and_stops_at_ten(tmp_path):
    path,history=historical_ledger(tmp_path)
    with pytest.raises(CopyFailure,match='COPY_BUDGET_EXCEEDED'):CopyBudget(path).reserve()
    budget=CopyBudget(path,max_requests=10,budget_usd=.1)
    for _ in range(4):budget.reserve()
    result=json.loads(path.read_text())
    assert result['calls'][:6]==history and len(result['calls'])==10
    assert sum(r['cost_ceiling_usd'] for r in result['calls'])==pytest.approx(.00906225+4*MAX_COST)
    with pytest.raises(CopyFailure,match='COPY_BUDGET_EXCEEDED'):budget.reserve()
    assert json.loads(path.read_text())==result


def test_expansion_does_not_override_dollar_limit(tmp_path):
    path,history=historical_ledger(tmp_path)
    with pytest.raises(CopyFailure,match='COPY_BUDGET_EXCEEDED'):
        CopyBudget(path,max_requests=10,budget_usd=.01).reserve()
    assert json.loads(path.read_text())['calls']==history


@pytest.mark.parametrize('limit',[6,10])
def test_settings_and_budget_accept_same_approved_limits(tmp_path,limit):
    settings=Settings(_env_file=None,copy_max_requests=limit)
    assert CopyBudget(tmp_path/'ledger',settings.copy_max_requests).max_requests==limit
    assert Settings(_env_file=None).copy_max_requests==6


@pytest.mark.parametrize('limits',[{'max_requests':11},{'budget_usd':.100001}])
def test_unapproved_limits_rejected(tmp_path,limits):
    with pytest.raises(ValueError):CopyBudget(tmp_path/'ledger',**limits)


@pytest.mark.parametrize('failure',['invalid_json','retryable_provider'])
def test_presentation_zero_retries_even_for_retryable_failures(setup,tmp_path,failure):
    app,client,headers,meta,path,_=setup;save(client,headers,path)
    def action(_):
        if failure=='retryable_provider':raise CopyFailure('COPY_PROVIDER_UNAVAILABLE',True)
        return reply(output_text='{invalid')
    adapter,calls,budget=provider(tmp_path,action,max_requests=10)
    app.state.copy_store.provider=adapter;app.state.copy_store.max_retries=0
    client.post(path,headers=headers,json=request(meta))
    result=client.get(path,headers=headers).json()
    assert result['status']=='failed' and len(result['attempts'])==len(calls)==1
    assert len(json.loads(budget.path.read_text())['calls'])==1
