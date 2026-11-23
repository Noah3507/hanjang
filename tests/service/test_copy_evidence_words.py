"""Rejected copy names the rule so a failed paid call can be diagnosed without exposing input."""
import json
import logging

import pytest

from app.schemas.upload import InputDraft
from app.services.copy_contract import CopyFailure
from app.services.copy_prompt import PROMPT_VERSION, SYSTEM_PROMPT, input_bound, provider_payload
from app.services.copy_validation import validate_copy

DRAFT = InputDraft.model_validate({'facts': {'store_name': '쿠지라 식당', 'product_name': '아부라소바', 'price_text': '10,500원',
                                             'address': '서울 비공개로 1', 'instagram_handle': '@private_shop'},
                                   'mood': 'warm', 'product_features': '진한 소스, 쫄깃한 굵은 면'})


def reply(headline, body='', cta='보기'):
    variants = [{'strategy': s, 'copy': {'headline': headline if s == 'emotional' else f'{s} 제목', 'body': body if s == 'emotional' else '',
                                          'cta': cta}} for s in ('emotional', 'price', 'visual', 'brand')]
    return json.dumps({'variants': variants}, ensure_ascii=False)


@pytest.mark.parametrize('headline, reason', [
    ('수제 [[product_name]] 한 그릇', 'unsupplied claim 수제'),
    ('치즈를 듬뿍 올린 오늘', 'unsupplied claim 치즈'),
    ('동네 인기 메뉴', 'unsupplied claim 인기'),
    ('3분 만에 나오는 한 그릇', 'unsupplied number 3'),
    ('단돈 9,900원', 'rewritten price'),
    ('[[menu]] 출시', 'unknown placeholder'),
    ('@private_shop 에서 만나요', 'url or handle'),
])
def test_rejection_names_the_rule(headline, reason):
    with pytest.raises(CopyFailure) as caught:
        validate_copy(reply(headline), DRAFT)
    assert caught.value.code == 'COPY_FACTS_VIOLATION' and caught.value.retryable
    assert caught.value.reason == reason


def test_private_field_reason_does_not_repeat_the_value():
    draft = DRAFT.model_copy(update={'use_address_for_copy': False})
    with pytest.raises(CopyFailure) as caught:
        validate_copy(reply('서울 비공개로 1 근처 가게'), draft)
    assert caught.value.reason == 'private contact field' and '비공개' not in caught.value.reason


@pytest.mark.parametrize('headline', ['맛있는 [[product_name]] 한 그릇', '진한 풍미가 가득한 오늘', '쫄깃하고 고소한 한입', '바삭하고 달콤하게'])
def test_taste_words_pass_without_any_features(headline):
    draft = DRAFT.model_copy(update={'product_features': None})
    assert validate_copy(reply(headline), draft).variants[0].ad_copy.headline


def test_supplied_feature_words_and_price_placeholder_pass():
    result = validate_copy(reply('진한 소스에 쫄깃한 면', '가격: [[price_text]]'), DRAFT)
    assert result.variants[0].ad_copy.headline == '진한 소스에 쫄깃한 면'
    assert result.variants[0].ad_copy.body == '가격: 10,500원'


def test_prompt_names_the_evidence_rule_and_still_fits_the_input_limit():
    assert PROMPT_VERSION == 'copy-v6-menu-identity'
    assert '맛·식감 표현은 써도 된다' in SYSTEM_PROMPT and '입력에 같은 말이 있을 때만' in SYSTEM_PROMPT and '[[price_text]]' in SYSTEM_PROMPT
    typical = DRAFT.model_copy(update={'product_features': '가' * 300})
    assert input_bound(provider_payload(typical, {'visual_hints': []})) <= 6000


def test_store_logs_rule_and_token_but_not_copy_text(caplog):
    from app.services.copy_store import log
    caplog.set_level(logging.WARNING, logger=log.name)
    failure = CopyFailure('COPY_FACTS_VIOLATION', True, reason='unsupplied claim 맛있')
    log.warning('copy attempt %s rejected: %s (%s)', 1, failure.code, failure.reason)
    assert 'unsupplied claim 맛있' in caplog.text
