"""Offline only: fake SDK objects, blocked sockets, no real API credentials."""
from io import BytesIO
import json
from types import SimpleNamespace
import pytest
import httpx
import openai
from PIL import Image
from app.config import Settings
from app.schemas.upload import InputDraft
from app.services.copy_provider import MockCopyProvider, build_copy_provider
from app.services.copy_contract import CopyFailure
from app.services.copy_validation import validate_copy
from app.services.copy_glyphs import supported_text, supported_codepoints
from app.services.copy_budget import CopyBudget, MAX_COST
from app.services.copy_openai import OpenAICopyProvider
from app.services.render_execution import RenderExecution, RenderFailure
from test_copy import setup, save, request, draft

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    original=socket.socket.connect
    def blocked(sock, address):
        if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
            return original(sock,address)  # Windows asyncio's internal socket pair
        raise AssertionError('External network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', blocked)

def reply(**changes):
    values={'usage':SimpleNamespace(input_tokens=100,output_tokens=200),'status':'completed',
        'output_text':MockCopyProvider().generate({}).text,'output':[]}
    values.update(changes);return SimpleNamespace(**values)

def provider(tmp_path, action, **limits):
    calls=[]
    def create(**kw):
        calls.append(kw)
        return action(kw)
    # Metadata requests are forbidden as well as real network requests.
    client=SimpleNamespace(responses=SimpleNamespace(create=create))
    budget=CopyBudget(tmp_path/'ledger.json',**limits)
    return OpenAICopyProvider('gpt-5.4-mini-2026-03-17','offline-test-marker',True,budget,client),calls,budget

@pytest.mark.parametrize('text',['한글 광고, 상품을 만나보세요!','ABC xyz 123, 10,500원 / ₩5,000',
    '“따뜻한 한 끼” · (선택) - 가격: 10,500원','주소 123번길 @example.shop'])
def test_actual_font_normal_text(text):
    assert supported_codepoints() and supported_text(text)

@pytest.mark.parametrize('text',['🍜','👩\u200d🍳','♥\ufe0f','1\ufe0f\u20e3','a\u200db','x\ufe0f','\U0010ffff','☀'])
def test_generated_glyph_rejection(text):
    body=json.loads(MockCopyProvider().generate({}).text)
    body['variants'][0]['copy']['headline']=text
    with pytest.raises(CopyFailure) as caught:validate_copy(json.dumps(body),InputDraft.model_validate(draft()))
    assert caught.value.code=='COPY_GLYPH_UNSUPPORTED' and caught.value.retryable

def test_unsupported_facts_preserved_until_renderer():
    d=InputDraft.model_validate(draft());d.facts.store_name='원문 가게 🍜'
    copy=validate_copy(MockCopyProvider().generate({}).text,d)
    assert d.facts.store_name=='원문 가게 🍜'
    raw=BytesIO();Image.new('RGB',(400,300),'orange').save(raw,'PNG')
    with pytest.raises(RenderFailure) as caught:RenderExecution()(d,copy,raw.getvalue())
    assert caught.value.code=='RENDER_UNSUPPORTED_GLYPH'
    assert d.facts.store_name=='원문 가게 🍜'

def test_structured_output_parameters_and_exact_dispatch_count(tmp_path):
    p,calls,budget=provider(tmp_path,lambda _:reply())
    assert p.generate({}).usage.estimated_cost_usd==pytest.approx(.000975)
    p.generate({})
    data=json.loads(budget.path.read_text())
    assert len(data['calls'])==len(calls)==2
    assert all(r['state']=='completed' and r['usage_known'] for r in data['calls'])
    assert calls[0]['text']['format']['strict'] and calls[0]['store'] is False
    assert calls[0]['max_output_tokens']==2048

@pytest.mark.parametrize('kind,code,retryable',[('timeout','COPY_PROVIDER_TIMEOUT',False),('rate','COPY_RATE_LIMIT',True),
    ('quota','COPY_RATE_LIMIT',False),('auth','COPY_AUTH_FAILED',False),('missing','COPY_MODEL_UNAVAILABLE',False)])
def test_sdk_errors_are_sanitized_and_counted(tmp_path,kind,code,retryable,capsys,caplog):
    marker='private-error-marker-never-log'
    req=httpx.Request('POST','https://api.openai.com/v1/responses')
    def action(_):
        if kind=='timeout':raise openai.APITimeoutError(request=req)
        typ,status={'rate':(openai.RateLimitError,429),'quota':(openai.RateLimitError,429),
            'auth':(openai.AuthenticationError,401),'missing':(openai.NotFoundError,404)}[kind]
        raise typ(marker,response=httpx.Response(status,request=req),body={'code':'insufficient_quota' if kind=='quota' else 'rate_limit_exceeded'})
    p,calls,budget=provider(tmp_path,action)
    with pytest.raises(CopyFailure) as caught:p.generate({})
    assert caught.value.code==code and caught.value.retryable==retryable
    assert len(calls)==1
    data=budget.path.read_text();r=json.loads(data)['calls'][0]
    assert r['state']=='failed' and r['cost_ceiling_usd']==MAX_COST and not r['usage_known']
    assert marker not in str(caught.value)+data+caplog.text+capsys.readouterr().out
    assert 'offline-test-marker' not in data

@pytest.mark.parametrize('result,code',[(reply(output=[SimpleNamespace(content=[SimpleNamespace(type='refusal')])]),'COPY_REFUSED'),
    (reply(status='incomplete',output_text=''),'COPY_OUTPUT_INCOMPLETE'),(reply(usage=None),'COPY_USAGE_UNKNOWN'),
    (reply(usage=SimpleNamespace(input_tokens=-1,output_tokens=0)),'COPY_USAGE_UNKNOWN')])
def test_refusal_incomplete_unknown_never_retried_by_adapter(tmp_path,result,code):
    p,calls,budget=provider(tmp_path,lambda _:result)
    with pytest.raises(CopyFailure) as caught:p.generate({})
    assert caught.value.code==code and not caught.value.retryable and len(calls)==1
    r=json.loads(budget.path.read_text())['calls'][0]
    assert r['usage_known']==(code!='COPY_USAGE_UNKNOWN')

@pytest.mark.parametrize('limits',[{'max_requests':0},{'budget_usd':0},{'budget_usd':MAX_COST/2}])
def test_budget_block_sends_no_request(tmp_path,limits):
    p,calls,_=provider(tmp_path,lambda _:reply(),**limits)
    with pytest.raises(CopyFailure) as caught:p.generate({})
    assert caught.value.code=='COPY_BUDGET_EXCEEDED' and calls==[]

def test_retry_ledger_matches_all_generation_attempts(setup,tmp_path):
    app,c,h,m,path,_=setup;save(c,h,path)
    sequence=iter([reply(output_text='{bad json'),reply()])
    p,calls,budget=provider(tmp_path,lambda _:next(sequence))
    app.state.copy_store.provider=p
    c.post(path,headers=h,json=request(m))
    result=c.get(path,headers=h).json()
    assert result['status']=='completed' and len(result['attempts'])==len(calls)==len(json.loads(budget.path.read_text())['calls'])==2

def test_glyph_retry_and_retry_disabled(setup):
    app,c,h,m,path,_=setup;save(c,h,path)
    good=MockCopyProvider().generate({})
    bad=json.loads(good.text);bad['variants'][0]['copy']['headline']='🍜'
    from app.services.copy_contract import ProviderResult
    replies=iter([ProviderResult(json.dumps(bad)),good])
    app.state.copy_store.provider.generate=lambda _:next(replies)
    c.post(path,headers=h,json=request(m))
    result=c.get(path,headers=h).json()
    assert result['status']=='completed' and result['attempts'][0]['error_code']=='COPY_GLYPH_UNSUPPORTED'

def test_configured_no_retry_and_exhausted_budget_stop_dispatch(setup,tmp_path):
    app,c,h,m,path,_=setup;save(c,h,path)
    p,calls,budget=provider(tmp_path,lambda _:reply(output_text='{bad'),max_requests=1)
    app.state.copy_store.provider=p
    c.post(path,headers=h,json=request(m))
    result=c.get(path,headers=h).json()
    assert result['status']=='failed' and len(calls)==1 and len(result['attempts'])==2
    assert result['attempts'][1]['error_code']=='COPY_BUDGET_EXCEEDED'
    # Second app attempt was locally denied, not an HTTP generation request.
    assert len(json.loads(budget.path.read_text())['calls'])==1
    app.state.copy_store.max_retries=0
    c.post(path,headers=h,json=request(m))
    assert len(c.get(path,headers=h).json()['attempts'])==1 and len(calls)==1

def test_over_budget_usage_is_recorded_not_refunded(tmp_path):
    p,calls,budget=provider(tmp_path,lambda _:reply(usage=SimpleNamespace(input_tokens=7000,output_tokens=200)))
    with pytest.raises(CopyFailure) as caught:p.generate({})
    assert caught.value.code=='COPY_USAGE_LIMIT_EXCEEDED' and not caught.value.retryable
    r=json.loads(budget.path.read_text())['calls'][0]
    assert r['usage_known'] and r['input_tokens']==7000

@pytest.mark.parametrize('updates',[{'copy_max_requests':7},{'copy_budget_usd':.11},{'copy_max_retries':2},{'copy_budget_usd':float('nan')}])
def test_limits_cannot_silently_exceed_approval(updates):
    with pytest.raises(ValueError):Settings(_env_file=None,**updates)

def test_sdk_constructor_keeps_no_retries_and_no_key_leak(tmp_path,monkeypatch):
    kwargs=[]
    monkeypatch.setattr(openai,'OpenAI',lambda **kw:kwargs.append(kw) or SimpleNamespace(responses=SimpleNamespace(create=lambda **_:reply())))
    p=OpenAICopyProvider('gpt-5.4-mini-2026-03-17','offline-test-marker',True,CopyBudget(tmp_path/'ledger.json'))
    p.generate({})
    assert kwargs[0]['max_retries']==0 and kwargs[0]['timeout']==30.
    settings=Settings(_env_file=None,OPENAI_API_KEY='offline-test-marker')
    assert 'offline-test-marker' not in repr(settings)
    assert build_copy_provider(settings).name=='mock'
