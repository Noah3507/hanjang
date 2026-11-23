import json
from pathlib import Path
import pytest
from app.schemas.upload import InputDraft
from app.services.copy_validation import validate_copy
from app.services.copy_quality import review_ad_copy
from app.services.copy_provider import MockCopyProvider
from app.services.copy_contract import CopyFailure
from app.services.copy_prompt import SYSTEM_PROMPT,input_bound

FIXTURE=Path('tests/fixtures/copy/ad_quality_v1.json')


def test_fixed_advertising_copy_is_fact_bound_and_fixture_only():
    for case in json.loads(FIXTURE.read_text(encoding='utf-8')).values():
        draft=InputDraft.model_validate({'facts':case['facts'],'mood':'warm','product_features':case['product_features']})
        before=draft.model_dump()
        result=validate_copy(json.dumps({'variants':case['variants']},ensure_ascii=False),draft)
        assert len(result.variants)==4
        # Historical Phase16 fixtures repeat bodies across strategies; the new
        # advisory must identify that repetition, not certify these as LLM quality.
        repeated=len({v.ad_copy.body for v in result.variants})<4
        assert review_ad_copy(result.variants)==(['COPY_REPETITION_REVIEW'] if repeated else [])
        assert draft.model_dump()==before
        assert all('[[' not in t for v in result.variants for t in v.ad_copy.model_dump().values())
    mock=json.loads(MockCopyProvider().generate({}).text)
    assert mock['variants'][1]['copy']['headline']=='가격을 확인하고 선택하세요'
    assert '한 그릇에 담은 진한 풍미' not in str(mock)


def test_final_text_advisory_does_not_rewrite_or_reject_mock_contract():
    case=json.loads(FIXTURE.read_text(encoding='utf-8'))['aburasoba']
    draft=InputDraft.model_validate({'facts':case['facts'],'mood':'warm'})
    raw=json.loads(MockCopyProvider().generate({}).text)
    raw['variants'][0]['copy'].update(headline='[[store_name]]',body='쿠지라스토랑')
    result=validate_copy(json.dumps(raw,ensure_ascii=False),draft)
    original=result.model_dump_json(by_alias=True)
    warnings=review_ad_copy(result.variants)
    assert {'COPY_SERVICE_LANGUAGE_REVIEW','COPY_REPETITION_REVIEW'}<=set(warnings)
    assert result.model_dump_json(by_alias=True)==original


@pytest.mark.parametrize('claim',['인증받은 상품','수상한 브랜드','품절 임박','무료 배송','판매량 보장','최저가 상품'])
def test_new_unprovided_claims_rejected_after_binding(claim):
    case=json.loads(FIXTURE.read_text(encoding='utf-8'))['aburasoba']
    d=InputDraft.model_validate({'facts':case['facts'],'mood':'warm'})
    raw=json.loads(MockCopyProvider().generate({}).text);raw['variants'][0]['copy']['body']=claim
    with pytest.raises(CopyFailure):validate_copy(json.dumps(raw,ensure_ascii=False),d)


def test_ad_direction_prompt_keeps_input_bound_and_vendor_contract():
    assert input_bound({})<6000
    assert all(s+':' in SYSTEM_PROMPT for s in ('emotional','price','visual','brand'))
    assert '기능 안내' in SYSTEM_PROMPT and '[[price_text]]' in SYSTEM_PROMPT
