"""Conservative evidence checks, not a semantic truth verifier."""
import re
from app.schemas.copy import Variants, Copy, STRATEGIES
from app.services.copy_contract import CopyFailure

CLAIMS = re.compile(
    r'할인|이벤트|특가|무료|증정|쿠폰|한정|국산|국내산|수입산|원산지|유기농|무첨가|저당|'
    r'면역|다이어트|항암|치료|효능|신선|매일|수제|최고|인기|베스트|바삭|고소|달콤|부드러|'
    r'촉촉|쫄깃|매콤|담백|진한|맛있|풍미|치즈|우유|버터|밀가루|꿀|딸기|초콜릿|견과|크림|'
    r'제주|한우|유기농|100%|단백질|저칼로리')

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
            # Names/prices can be bound verbatim without asking the model to rewrite them.
            for key, value in allowed.items():
                text = text.replace('[['+key+']]', value)
            if '[[' in text or ']]' in text or re.search(r'https?://|www\.|@', text):
                raise CopyFailure('COPY_FACTS_VIOLATION', True)
            for private in [facts['instagram_handle'], facts['address'] if not draft.use_address_for_copy else None]:
                if private and private in text:
                    raise CopyFailure('COPY_FACTS_VIOLATION', True)
            # Supplied facts are not rewritten; reject newly invented numeric claims.
            remaining = text
            for supplied in sorted(allowed.values(), key=len, reverse=True):
                remaining = remaining.replace(supplied, '')
            # A known numeric token must not authorize a rewritten price spelling.
            # Currency amounts are allowed only as part of a verbatim bound fact.
            if re.search(r'\d[\d,.\s]*(?:원|달러)|[₩$]\s*\d', remaining):
                raise CopyFailure('COPY_FACTS_VIOLATION', True)
            if any(number not in set(re.findall(r'\d[\d,.%]*', evidence)) for number in re.findall(r'\d[\d,.%]*', remaining)):
                raise CopyFailure('COPY_FACTS_VIOLATION', True)
            if any(match.group() not in evidence for match in CLAIMS.finditer(remaining)):
                raise CopyFailure('COPY_FACTS_VIOLATION', True)
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
