"""Advisory checks on final fact-bound copy; never rewrite or certify prose."""
import re

SERVICE_LANGUAGE=re.compile(r'사진(?:을|를|으로)?\s*확인|상품\s*정보[를을]?\s*확인|가격[을를]?\s*확인|표시된\s*상품|입력[된한]?\s*정보')


def review_ad_copy(variants, ad_goal='menu_promotion'):
    warnings=[]
    headlines=set()
    bodies=set()
    for variant in variants:
        cta=variant.ad_copy.cta
        if cta and ad_goal=='menu_promotion' and re.search(r'주문|방문|들러|오세요',cta):warnings.append('COPY_GOAL_REVIEW')
        if cta and ad_goal=='store_visit' and re.search(r'사진|정보|가격|상품\s*확인',cta):warnings.append('COPY_GOAL_REVIEW')
        if any(re.search(r'부담\s*(?:없|없이)|가성비|저렴',v) for v in variant.ad_copy.model_dump().values()):warnings.append('COPY_PRICE_VALUE_REVIEW')
        values=list(variant.ad_copy.model_dump().values())
        if any(SERVICE_LANGUAGE.search(v) for v in values):warnings.append('COPY_SERVICE_LANGUAGE_REVIEW')
        normalized=[re.sub(r'[\s\W_]+','',v).lower() for v in values if v]
        if any(a==b or min(len(a),len(b))>=8 and (a in b or b in a) for i,a in enumerate(normalized) for b in normalized[i+1:]):
            warnings.append('COPY_REPETITION_REVIEW')
        # Cross-strategy repetition is advisory, never a new paid retry reason.
        for text,seen,minimum in [(variant.ad_copy.headline,headlines,4),(variant.ad_copy.body,bodies,8)]:
            key=re.sub(r'[\s\W_]+','',text).lower()
            if len(key)>=minimum:
                if key in seen:warnings.append('COPY_REPETITION_REVIEW')
                seen.add(key)
    return sorted(set(warnings))
