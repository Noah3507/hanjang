import json
import pytest
from app.schemas.upload import InputDraft
from app.services.copy_contract import CopyFailure, ProviderResult
from app.services.copy_provider import MockCopyProvider
from app.services.copy_validation import validate_copy
from test_copy import setup, save, request


def validate(product, price, text, field='body'):
    draft=InputDraft.model_validate({'facts':{'store_name':'가게','product_name':product,'price_text':price},'mood':'warm'})
    before=draft.model_dump()
    raw=json.loads(MockCopyProvider().generate({}).text)
    raw['variants'][0]['copy'][field]=text
    try:return validate_copy(json.dumps(raw,ensure_ascii=False),draft)
    finally:assert draft.model_dump()==before


@pytest.mark.parametrize('product,price,text',[
    ('국수','10,500원','[[price_text]]로 만나세요.'),
    ('국수','10,500원','10,500원로 만나세요.'),
    ('국수','10,500원','가격은10,500원로 확인하세요.'),
    ('국수','10,500원','[[price_text]]로도 만나세요.'),
    ('국수','10,500원','[[product_name]]을 만나세요.'),
    ('라면','10,500원','[[product_name]]를 만나세요.'),
    ('아부라소바','10,500원','[[product_name]]은 여기 있습니다.'),
    ('라면','10,500원','라면와 함께하세요.'),
    ('국수','10,500원','국수이 여기 있습니다.'),
    ('물','10,500원','[[product_name]]으로 만나세요.'),
    ('국수',' 10,500 원 ','[[price_text]]로 만나세요.'),
])
def test_reject_wrong_particles_after_binding_and_literal_facts(product,price,text):
    with pytest.raises(CopyFailure,match='COPY_PARTICLE_INVALID') as failure:validate(product,price,text)
    assert failure.value.retryable is False


@pytest.mark.parametrize('product,price,text',[
    ('국수','10,500원','[[price_text]]으로 만나세요.'),
    ('국수','10,500원','[[product_name]]를 만나세요.'),
    ('라면','10,500원','[[product_name]]을 만나세요.'),
    ('물','10,500원','[[product_name]]로 만나세요.'),
    ('국수','10,500원','국수와 함께하세요.'),
    ('라면','10,500원','라면과 함께하세요.'),
    ('국수','10,500원','국수가 여기 있습니다.'),
    ('라면','10,500원','라면이 여기 있습니다.'),
    ('국수','10,500원','국수는 여기 있습니다.'),
    ('라면','10,500원','라면은 여기 있습니다.'),
    ('SKU-500',' 10,500 원 ','가격: [[price_text]] / 상품: [[product_name]]'),
])
def test_correct_particles_and_neutral_forms_preserve_facts(product,price,text):
    result=validate(product,price,text)
    assert price in result.variants[0].ad_copy.body or product in result.variants[0].ad_copy.body


@pytest.mark.parametrize('field',['headline','body','cta'])
def test_every_copy_field_is_checked(field):
    with pytest.raises(CopyFailure,match='COPY_PARTICLE_INVALID'):validate('국수','10,500원','[[price_text]]로',field)


@pytest.mark.parametrize('fact',['SKU-500','500','Cafe'])
def test_unknown_pronunciation_requires_review_not_guessing(fact):
    with pytest.raises(CopyFailure,match='COPY_PARTICLE_REVIEW_REQUIRED') as failure:validate(fact,'10,500원','[[product_name]]을 확인하세요.')
    assert not failure.value.retryable


def test_bad_particle_does_not_trigger_provider_retry(setup):
    app,client,headers,meta,path,_=setup;save(client,headers,path)
    raw=json.loads(MockCopyProvider().generate({}).text)
    raw['variants'][0]['copy']['body']='[[price_text]]로 만나세요.'
    calls=[]
    def fake(payload):calls.append(payload);return ProviderResult(json.dumps(raw))
    app.state.copy_store.provider.generate=fake
    client.post(path,headers=headers,json=request(meta))
    result=client.get(path,headers=headers).json()
    assert result['status']=='failed' and result['error']['code']=='COPY_PARTICLE_INVALID'
    assert len(calls)==len(result['attempts'])==1
    assert '한국어 조사' in result['error']['message']
