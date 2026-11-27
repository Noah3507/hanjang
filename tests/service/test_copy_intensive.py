import json
from types import SimpleNamespace as NS

import pytest

from app.services.copy_budget import CopyBudget
from app.services.copy_contract import CopyFailure
from app.services.copy_intensive import ExperimentRequest, IntensiveCopyExperiment, request_arguments

PAYLOAD = dict(store_name='shop', product_name='coffee', price_text=' 3000 ', mood='warm', product_features=None, visual_hints=[], ad_goal='order')


def test_default_limits_unchanged(tmp_path):
    for count, dollars in [(11, .1), (10, .11), (169, 5)]:
        with pytest.raises(ValueError):
            CopyBudget(tmp_path/'ledger.json', count, dollars)
    with pytest.raises(ValueError):
        CopyBudget(tmp_path/'ledger.json', 170, 5, approved_intensive=True)


def test_modes_and_original_input():
    for mode in ['single', 'pool', 'revise']:
        args, bound = request_arguments(ExperimentRequest(PAYLOAD, mode=mode, prior={'variants': []}))
        assert args['store'] is False and args['reasoning'] == {'effort': 'none'}
        assert args['service_tier'] == 'default'
        assert json.loads(args['input'][0]['content'][0]['text'])['product'] == PAYLOAD
        assert args['max_output_tokens'] == (4096 if mode == 'pool' else 2048)
        assert 0 < bound <= 24000
    with pytest.raises(CopyFailure):
        request_arguments(ExperimentRequest(PAYLOAD, model='unknown'))
    args, _ = request_arguments(ExperimentRequest(PAYLOAD, mode='pool'))
    schema = args['text']['format']['schema']
    assert 'Variant' in schema['$defs'] and '$defs' not in schema['properties']['sets']['items']
    args, _ = request_arguments(ExperimentRequest(PAYLOAD, direction='campaign', reasoning='low'))
    assert args['reasoning']['effort'] == 'low'


def test_pipeline_is_two_calls_and_blocks_invalid_pool(tmp_path):
    from app.schemas.upload import InputDraft
    from app.services.copy_contract import ProviderResult, ProviderUsage
    draft = InputDraft.model_validate({'facts': {'store_name': 'shop', 'product_name': 'coffee', 'price_text': '3000'}, 'mood': 'warm'})
    variants = {'variants': [{'strategy': s, 'copy': {'headline': 'hello '+s, 'body': '', 'cta': ''}}
                            for s in ('emotional', 'price', 'visual', 'brand')]}
    experiment = IntensiveCopyExperiment(tmp_path/'ledger.json', None, approved=True)
    modes = []
    def generated(request, capture):
        modes.append(request.mode)
        return ProviderResult(json.dumps({'sets': [variants, variants]} if request.mode == 'pool' else variants), ProviderUsage(100, 50, .001))
    experiment.generate = generated
    assert experiment.candidates_then_select(ExperimentRequest(PAYLOAD), draft, lambda *a: None).usage.estimated_cost_usd == .002
    assert modes == ['pool', 'select']
    modes.clear()
    def invalid(request, capture):
        modes.append(request.mode)
        return ProviderResult('{"sets":[{}]}', ProviderUsage(1, 1, .001))
    experiment.generate = invalid
    with pytest.raises(CopyFailure, match='COPY_EXPERIMENT_NO_VALID_CANDIDATES'):
        experiment.candidates_then_select(ExperimentRequest(PAYLOAD), draft, lambda *a: None)
    assert modes == ['pool']


def test_accounting_cached_and_history(tmp_path):
    ledger = tmp_path/'ledger.json'
    old = [{'id': str(i), 'cost_ceiling_usd': .001} for i in range(19)]
    ledger.write_text(json.dumps({'calls': old}))
    response = NS(usage=NS(input_tokens=100, output_tokens=50, input_tokens_details=NS(cached_tokens=20)),
                  status='completed', model='gpt-5.4-2026-03-05', output_text='{}')
    client = NS(responses=NS(create=lambda **kw: response))
    result = IntensiveCopyExperiment(ledger, client, approved=True).generate(ExperimentRequest(PAYLOAD, model=response.model), lambda *a: None)
    assert result.usage.estimated_cost_usd == pytest.approx((80*2.5+20*.25+50*15)/1e6)
    saved = json.loads(ledger.read_text())['calls']
    assert saved[:19] == old and len(saved) == 20 and saved[-1]['usage_known']


def test_failure_counted_and_no_retry(tmp_path):
    calls = []
    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('private detail')
    ledger = tmp_path/'ledger.json'
    exp = IntensiveCopyExperiment(ledger, NS(responses=NS(create=fail)), approved=True)
    with pytest.raises(CopyFailure, match='COPY_EXPERIMENT_PROVIDER_FAILED'):
        exp.generate(ExperimentRequest(PAYLOAD), lambda *a: None)
    saved = json.loads(ledger.read_text())['calls']
    assert len(calls) == len(saved) == 1 and saved[0]['cost_ceiling_usd'] > 0
    assert 'private' not in ledger.read_text()


def test_cumulative_ceiling_and_request_cap(tmp_path):
    path = tmp_path/'ledger.json'
    path.write_text(json.dumps({'calls': [{'id': str(i), 'cost_ceiling_usd': 0} for i in range(169)]}))
    exp = IntensiveCopyExperiment(path, None, approved=True)
    with pytest.raises(CopyFailure, match='COPY_BUDGET_EXCEEDED'):
        exp.generate(ExperimentRequest(PAYLOAD), lambda *a: None)
    path.write_text(json.dumps({'calls': [{'id': 'old', 'cost_ceiling_usd': 4.9999}]}))
    with pytest.raises(CopyFailure, match='COPY_BUDGET_EXCEEDED'):
        exp.generate(ExperimentRequest(PAYLOAD), lambda *a: None)


def test_request_logging_failure_does_not_dispatch_or_reserve(tmp_path):
    path = tmp_path/'ledger.json'
    def blocked(*args): raise OSError('local capture unavailable')
    exp = IntensiveCopyExperiment(path, None, approved=True)
    with pytest.raises(OSError):
        exp.generate(ExperimentRequest(PAYLOAD), blocked)
    assert not path.exists()


def test_invalid_reservation_never_writes_ledger(tmp_path):
    path = tmp_path/'ledger.json'
    budget = CopyBudget(path)
    for value in [-1, 0, float('nan'), float('inf'), True]:
        with pytest.raises(CopyFailure, match='COPY_BUDGET_INVALID'):
            budget._reserve(value)
    assert not path.exists()


def test_capture_precedes_dispatch_and_unknown_usage_keeps_reservation(tmp_path):
    events = []
    def create(**kw):
        events.append('dispatch')
        return NS(usage=None)
    def capture(args, response):
        events.append('request' if response is None else 'response')
    path = tmp_path/'ledger.json'
    exp = IntensiveCopyExperiment(path, NS(responses=NS(create=create)), approved=True)
    with pytest.raises(CopyFailure):
        exp.generate(ExperimentRequest(PAYLOAD), capture)
    assert events == ['request', 'dispatch', 'response']
    record = json.loads(path.read_text())['calls'][0]
    assert not record['usage_known'] and record['cost_ceiling_usd'] > 0
