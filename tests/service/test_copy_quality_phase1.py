import json
import pytest
from pathlib import Path
from app.schemas.upload import InputDraft
from app.services.copy_provider import MockCopyProvider
from app.services.copy_validation import validate_copy
from app.services.copy_contract import CopyFailure
from test_copy import setup,save,request
from test_openai_validation import no_network,provider as offline_provider,reply as offline_reply

CASES=json.loads(Path('tests/fixtures/copy/menu_quality_phase1.json').read_text(encoding='utf-8'))


def draft(product='아이스 아메리카노',features=None):
    return InputDraft.model_validate({'facts':{'store_name':'테스트 카페','product_name':product,'price_text':'4,000원'},'mood':'minimal','product_features':features})


def response(text):
    raw=json.loads(MockCopyProvider().generate({}).text)
    raw['variants'][0]['copy']['body']=text
    return json.dumps(raw,ensure_ascii=False)


@pytest.mark.parametrize('text',['매일 마시고 싶은 [[product_name]]','매일 먹고 싶은 한 조각'])
def test_daily_desire_is_subjective_not_a_production_frequency_claim(text):
    assert validate_copy(response(text),draft()).variants


@pytest.mark.parametrize('text',['매일 갓 볶는 원두','매일 만드는 케이크','매일 마시고 싶은 수제 커피','매일 마시고 싶은 우유 커피','국산 재료','한정 할인','저당 건강 커피'])
def test_subjective_exception_does_not_authorize_facts(text):
    with pytest.raises(CopyFailure):validate_copy(response(text),draft())


def test_cross_strategy_repetition_is_advisory_and_never_rewrites():
    from app.services.copy_quality import review_ad_copy
    raw=json.loads(MockCopyProvider().generate({}).text)
    for v in raw['variants']:v['copy']['headline']='같은 메뉴 같은 순간'
    result=validate_copy(json.dumps(raw,ensure_ascii=False),draft())
    before=result.model_dump_json()
    assert 'COPY_REPETITION_REVIEW' in review_ad_copy(result.variants)
    assert result.model_dump_json()==before


def test_menu_matrix_preserves_contract_and_labels_not_llm():
    from pathlib import Path
    from app.services.copy_prompt import input_bound,provider_payload
    cases=json.loads(Path('tests/fixtures/copy/menu_quality_phase1.json').read_text(encoding='utf-8'))
    assert len(cases)==8 and sum(c['input']['product_features'] is None for c in cases)==4
    for case in cases:
        assert case['provenance']=='human_authored_target_not_llm_output'
        d=InputDraft.model_validate(case['input']);before=d.model_dump()
        result=validate_copy(json.dumps(case['reference'],ensure_ascii=False),d)
        assert len(result.variants)==4 and len({v.strategy for v in result.variants})==4
        assert input_bound(provider_payload(d,{'visual_hints':[]}))<=6000
        for v in result.variants:
            assert d.facts.product_name in ' '.join(v.ad_copy.model_dump().values())
        price=next(v for v in result.variants if v.strategy=='price')
        assert d.facts.price_text in ' '.join(price.ad_copy.model_dump().values())
        assert d.model_dump()==before


def test_long_typical_features_do_not_consume_extra_budget_or_truncate():
    from app.services.copy_prompt import input_bound,provider_payload
    d=draft(features='가'*500);payload=provider_payload(d,{'visual_hints':[]})
    assert payload['product_features']=='가'*500
    assert input_bound(payload)<=6000


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['case_id'])
def test_fake_responses_adapter_delivers_prompt_and_no_unnecessary_retry(setup,tmp_path,case):
    from app.services.copy_prompt import SYSTEM_PROMPT,PROMPT_VERSION
    app,client,headers,meta,path,raw=setup
    output=json.dumps(case['reference'],ensure_ascii=False)
    provider,calls,budget=offline_provider(tmp_path,lambda kw:offline_reply(output_text=output))
    app.state.copy_store.provider=provider
    app.state.copy_store.max_retries=1
    value=case['input'];save(client,headers,path,value)
    assert client.post(path,headers=headers,json=request(meta,value)).status_code==202
    result=client.get(path,headers=headers).json()
    assert result['status']=='completed' and result['is_current']
    assert result['prompt_version']==PROMPT_VERSION and len(result['attempts'])==1 and len(calls)==1
    assert calls[0]['instructions']==SYSTEM_PROMPT and calls[0]['model']=='gpt-5.4-mini-2026-03-17'
    assert calls[0]['store'] is False and calls[0]['text']['format']['strict'] is True
    assert result['facts']['price_text']==value['facts']['price_text']
    assert not set(result['warnings'])&{'COPY_SERVICE_LANGUAGE_REVIEW','COPY_REPETITION_REVIEW'}
    assert len(json.loads(budget.path.read_text())['calls'])==1  # synthetic receipt only


def test_repetition_advisory_does_not_spend_a_retry(setup,tmp_path):
    app,client,headers,meta,path,raw=setup
    output=json.loads(MockCopyProvider().generate({}).text)
    for v in output['variants']:v['copy']['headline']='같은 메뉴 같은 순간'
    provider,calls,budget=offline_provider(tmp_path,lambda kw:offline_reply(output_text=json.dumps(output,ensure_ascii=False)))
    app.state.copy_store.provider=provider;app.state.copy_store.max_retries=1
    value=CASES[0]['input'];save(client,headers,path,value)
    client.post(path,headers=headers,json=request(meta,value))
    result=client.get(path,headers=headers).json()
    assert result['status']=='completed' and len(calls)==len(result['attempts'])==1
    assert 'COPY_REPETITION_REVIEW' in result['warnings']


@pytest.mark.skipif(__import__('os').getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['case_id'])
def test_authored_copy_fits_unchanged_v2_and_v3_renderers(case):
    from io import BytesIO
    from PIL import Image
    from app.services.render_execution import RenderExecution
    from app.services.template_v3 import TemplateInput,render_templates
    d=InputDraft.model_validate(case['input']);copies=validate_copy(json.dumps(case['reference'],ensure_ascii=False),d)
    buffer=BytesIO();Image.new('RGB',(400,400),'#d8c6ac').save(buffer,'PNG');raw=buffer.getvalue()
    assert len(RenderExecution()(d,copies,raw))==4
    for v in copies.variants:
        data=TemplateInput(d.facts.store_name,d.facts.product_name,d.facts.price_text,**v.ad_copy.model_dump())
        row=render_templates(data,raw,[v.strategy+'_a'])[0]
        assert not row['measurement']['invalid']
