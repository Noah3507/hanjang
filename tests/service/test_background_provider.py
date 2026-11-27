from io import BytesIO
import base64
import json
from types import SimpleNamespace as NS
import pytest
from PIL import Image
from app.services.background_provider import BackgroundBudget,OpenAIBackgroundProvider,background_prompt


def test_explicit_paid_gate_and_retry_gate(tmp_path):
    for paid,retries in [(False,0),(True,2)]:
        p=OpenAIBackgroundProvider(NS(max_retries=retries),tmp_path/'ledger.json',allow_paid=paid)
        with pytest.raises(ValueError):p.generate('coffee-dark','x',lambda *a:None)
    assert not (tmp_path/'ledger.json').exists()


def test_separate_ledger_never_accepts_copy_history(tmp_path):
    path=tmp_path/'copy.json';path.write_text('{"calls":[]}');before=path.read_bytes()
    with pytest.raises(ValueError):BackgroundBudget(path).reserve('x')
    assert path.read_bytes()==before


def test_budget_cap_duplicate_failure_and_unknown(tmp_path):
    b=BackgroundBudget(tmp_path/'ledger.json');ident=b.reserve('x');b.record(ident,state='failed')
    with pytest.raises(ValueError):b.reserve('x')
    for i in range(15):b.reserve(str(i))
    with pytest.raises(ValueError):b.reserve('seventeenth')
    data=json.loads(b.path.read_text());assert len(data['calls'])==16 and sum(c['cost_ceiling_usd'] for c in data['calls'])==4


def test_text_only_generation_and_usage(tmp_path):
    s=BytesIO();Image.new('RGB',(1024,1536),'white').save(s,'PNG');calls=[]
    response=NS(usage=NS(input_tokens_details=NS(text_tokens=300,image_tokens=0),output_tokens=1132),data=[NS(b64_json=base64.b64encode(s.getvalue()).decode())])
    def create(**kw):calls.append(kw);return response
    client=NS(max_retries=0,images=NS(generate=create))
    p=OpenAIBackgroundProvider(client,tmp_path/'image.json',allow_paid=True)
    result=p.generate('noodle-editorial','one',lambda *a:None)
    assert result.cost_usd==pytest.approx(.03546) and len(calls)==1
    assert set(calls[0])=={'model','prompt','n','size','quality','output_format','background','moderation','extra_body'}
    assert 'image' not in calls[0] and 'user' not in calls[0]
    with pytest.raises(ValueError):background_prompt('private shop name')


def test_failed_dispatch_has_no_retry_and_keeps_cost(tmp_path):
    calls=[]
    def fail(**kw):calls.append(kw);raise RuntimeError('private provider details')
    p=OpenAIBackgroundProvider(NS(max_retries=0,images=NS(generate=fail)),tmp_path/'image.json',allow_paid=True)
    with pytest.raises(RuntimeError,match='no retry'):p.generate('coffee-dark','one',lambda *a:None)
    data=json.loads(p.budget.path.read_text());assert len(calls)==1 and data['calls'][0]['cost_ceiling_usd']==.25
    assert 'private provider' not in p.budget.path.read_text()


def test_dollar_cap_and_overrun_stop_future_calls(tmp_path):
    budget = BackgroundBudget(tmp_path/'image.json')
    ident = budget.reserve('one')
    budget.record(ident, cost_ceiling_usd=4.8)
    with pytest.raises(ValueError, match='exhausted'):
        budget.reserve('two')
    budget.record(ident, cost_ceiling_usd=.3, reservation_exceeded=True)
    with pytest.raises(ValueError, match='stopped'):
        budget.reserve('two')


@pytest.mark.parametrize('usage', [None, NS(input_tokens_details=NS(text_tokens=10,image_tokens=1),output_tokens=1132)])
def test_missing_or_unexpected_usage_keeps_reservation(tmp_path, usage):
    response = NS(usage=usage, data=[])
    client = NS(max_retries=0, images=NS(generate=lambda **kw: response))
    provider = OpenAIBackgroundProvider(client,tmp_path/'image.json',allow_paid=True)
    with pytest.raises(RuntimeError):
        provider.generate('coffee-dark','one',lambda *a:None)
    call = json.loads(provider.budget.path.read_text())['calls'][0]
    assert call['cost_ceiling_usd']==.25 and call['usage_known'] is False


def test_response_capture_failure_still_records_known_usage(tmp_path):
    response = NS(usage=NS(input_tokens_details=NS(text_tokens=300,image_tokens=0),output_tokens=1132),data=[])
    client = NS(max_retries=0,images=NS(generate=lambda **kw:response))
    provider = OpenAIBackgroundProvider(client,tmp_path/'image.json',allow_paid=True)
    def capture(args,reply):
        if reply is not None:
            raise OSError('local disk failure')
    with pytest.raises(RuntimeError):
        provider.generate('coffee-dark','one',capture)
    call = json.loads(provider.budget.path.read_text())['calls'][0]
    assert call['usage_known'] is True and call['cost_ceiling_usd']==pytest.approx(.03546)
