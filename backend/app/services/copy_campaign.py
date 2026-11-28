"""Bounded campaign recipe, reusing the intensive art direction and B's limits."""
from app.services.copy_intensive import EDITORIAL
from app.services.copy_prompt_v8_1 import GOAL_DIRECTIONS
from app.services.copy_contract import CopyFailure

VERSION = 'copy-campaign-pool-choose-slots-5-limits1'
MODEL = 'gpt-5.4-2026-03-05'
INPUT_LIMIT = 12000


def instructions_for(payload):
    goal = payload.get('ad_goal')
    if not isinstance(goal, str) or goal not in GOAL_DIRECTIONS:
        raise CopyFailure('COPY_GOAL_INVALID')
    intent = {
        'menu_promotion': '상품 자체를 먹거나 쓰고 싶은 마음이 들게 한다. 소비자에게 메뉴판을 확인하는 방법을 설명하지 않는다. CTA는 상품에 대한 짧은 권유 또는 빈 문자열.',
        'store_visit': '상품을 계기로 가게에 들르고 싶은 마음이 들게 한다. 실제 주소·영업시간·매장 경험은 만들지 않는다. CTA는 방문 초대 또는 빈 문자열.',
        'order': '지금 이 상품을 주문하고 싶은 마음이 들게 한다. 주문 수단을 특정하지 않는다. CTA는 주문 권유 또는 빈 문자열.',
    }[goal]
    limits_direction = ('\ntemplate_copy_limits는 치환 후 공백까지 센 실제 표시 글자 수 기준이다. 전략별 soft 이내를 목표로 자연스럽게 쓰고 hard 초과는 피한다. hard는 템플릿 축소/가독성 측정값이지 사실을 줄이거나 출력 스키마를 바꾸라는 지시가 아니다. 긴 상품명 자체는 수정하지 않는다.' if payload.get('template_copy_limits') else '')
    return EDITORIAL + '\n이 광고의 목적: ' + intent + limits_direction + '''
소비자가 듣고 싶은 한마디를 쓰고 '선택하기 좋은 메뉴/한 그릇/메뉴판/선택지'라는 설명으로 끝내지 않는다. 고객에게 바로 말하는 짧고 생생한 구어체를 우선한다. 전략마다 제목의 초점과 문장 리듬을 달리하고 본문과 CTA로 제목을 다시 설명하지 않는다.
displayed_facts_by_strategy는 서버가 보장하는 독립 사실 슬롯이다. 목록에 있는 사실을 다시 나열할 의무는 없다. 다만 상품을 떠올리게 하는 자연스러운 메시지에 필요하면 상품·상호 placeholder를 한 번 쓸 수 있다. 사실 이름을 전부 피해서 어떤 메뉴에도 맞는 문장이 되지 않게 한다. 가격형 제목은 별도 가격칸의 숫자를 복창하는 대신 지금 이 메뉴를 고를 장면을 짧게 권한다. '가격칸/표시 가격/사진/템플릿' 같은 제작·안내 언어는 쓰지 않는다. 목록에 없는 필수 사실은 해당 placeholder를 한 번 포함해 누락을 막는다.
브랜드형은 가게가 소비자에게 건네는 초대다. 고객이 이미 떠올리거나 찾는다는 습관·친숙함을 서술하지 않는다. 보탤 브랜드 근거가 없으면 짧은 제목만 남기고 본문은 비운다.
CTA는 소비자가 할 수 있는 행동을 담은 짧은 권유다. 음식의 '한 젓가락 하세요', 음료의 '한 모금 쉬어가세요'처럼 구체적인 소비 행동을 생각하되 예시를 모든 광고에 복사하지 않는다. '맛이 당긴다'라는 감각을 '당겨보세요/지금 당겨요'라는 어색한 명령으로 바꾸지 않는다. 상품을 권할 말이 자연스럽지 않으면 빈 CTA를 쓴다. 본문은 새 정보나 장면이 있을 때만 쓰되 모든 본문을 기계적으로 비우지는 않는다.
최종 JSON 전에 제목과 CTA를 이어 읽고, 어색한 동사 결합·메뉴판 안내·고객 선호 단정이 있으면 그 필드만 바로잡는다. 새로운 사실·가격 가치 판단을 만들지 않는다. 가격 언급이 필요하면 [[price_text]]를 조사 없는 독립 구절로 둔다.'''
