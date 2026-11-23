"""Conservative evidence checks, not a semantic truth verifier."""
import re
from app.schemas.copy import Variants, Copy, STRATEGIES
from app.services.copy_contract import CopyFailure
from app.services.copy_glyphs import supported_text
from app.services.copy_particles import check_fact_particles

# Factual claims a customer could rely on: offers, origin, ingredients (allergies), health, popularity, freshness.
# They pass only when the same words appear in the user's facts or product_features.
CLAIMS = re.compile(
    r'할인|이벤트|특가|무료|증정|쿠폰|한정|국산|국내산|수입산|원산지|유기농|무첨가|저당|'
    r'면역|다이어트|항암|치료|효능|신선|매일|수제|최고|인기|베스트|'
    r'치즈|우유|버터|밀가루|꿀|딸기|초콜릿|견과|크림|'
    r'제주|한우|100%|단백질|저칼로리|인증|수상|특허|완치|보장|배송|판매량|누적판매|재고|완판|품절|최저가|가성비|저렴')
# General taste and texture words (맛있다, 풍미, 진한, 고소, 달콤, 바삭, 쫄깃, 촉촉, 부드러운, 담백, 매콤) are allowed
# without user input: they describe an impression, not a checkable fact, and let copy be written from the photo alone.

def validate_copy(raw: str, draft):
    try:
        body = Variants.model_validate_json(raw)
    except Exception:
        raise CopyFailure('COPY_SCHEMA_INVALID', True) from None
    facts = draft.facts.model_dump()
    allowed = {k: facts[k] for k in ('store_name', 'product_name', 'price_text')}
    if draft.use_address_for_copy and facts['address']:
        allowed['address'] = facts['address']
    evidence = '\n'.join([*allowed.values(), draft.product_features or ''])
    for variant in body.variants:
        values = {}
        for field, text in variant.ad_copy.model_dump().items():
            if not supported_text(text):
                raise CopyFailure('COPY_GLYPH_UNSUPPORTED', True)
            # Names/prices can be bound verbatim without asking the model to rewrite them.
            for key, value in allowed.items():
                text = text.replace('[['+key+']]', value)
            if '[[' in text or ']]' in text:
                raise CopyFailure('COPY_FACTS_VIOLATION', True, reason='unknown placeholder')
            if re.search(r'https?://|www\.|@', text):
                raise CopyFailure('COPY_FACTS_VIOLATION', True, reason='url or handle')
            for private in [facts['instagram_handle'], facts['address'] if not draft.use_address_for_copy else None]:
                if private and private in text:
                    raise CopyFailure('COPY_FACTS_VIOLATION', True, reason='private contact field')
            # Supplied facts are not rewritten; reject newly invented numeric claims.
            remaining = text
            for supplied in sorted(allowed.values(), key=len, reverse=True):
                remaining = remaining.replace(supplied, '')
            # A known numeric token must not authorize a rewritten price spelling.
            # Currency amounts are allowed only as part of a verbatim bound fact.
            if re.search(r'\d[\d,.\s]*(?:원|달러)|[₩$]\s*\d', remaining):
                raise CopyFailure('COPY_FACTS_VIOLATION', True, reason='rewritten price')
            known = set(re.findall(r'\d[\d,.%]*', evidence))
            for number in re.findall(r'\d[\d,.%]*', remaining):
                if number not in known:
                    raise CopyFailure('COPY_FACTS_VIOLATION', True, reason=f'unsupplied number {number}')
            for match in CLAIMS.finditer(remaining):
                if match.group() not in evidence:
                    raise CopyFailure('COPY_FACTS_VIOLATION', True, reason=f'unsupplied claim {match.group()}')
            check_fact_particles(text, allowed)
            values[field] = text
        try:
            variant.ad_copy = Copy.model_validate(values)  # recheck lengths after fact binding
        except Exception:
            raise CopyFailure('COPY_SCHEMA_INVALID', True) from None
    body.variants.sort(key=lambda v: STRATEGIES.index(v.strategy))
    # Binding can make formerly different texts identical.
    try:
        return Variants.model_validate_json(body.model_dump_json(by_alias=True))
    except Exception:
        raise CopyFailure('COPY_SCHEMA_INVALID', True) from None
