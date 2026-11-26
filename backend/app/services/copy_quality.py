"""Advisory checks on final fact-bound copy; never rewrite or certify prose."""
import re

SERVICE_LANGUAGE=re.compile(r'사진(?:을|를|으로)?\s*확인|상품\s*정보[를을]?\s*확인|가격[을를]?\s*확인|표시된\s*상품|입력[된한]?\s*정보')
ORDER_ACTION=re.compile(r'주문(?:하|해|을|하기)|주문\s*(?:부탁|원하)')
VISIT_ACTION=re.compile(r'방문(?:하|해)|들러|매장.{0,6}(?:오세요|와\s*보)')
MENU_ACTION=re.compile(r'메뉴|골라|고르|선택|살펴|둘러|알아')
ANALYSIS_STYLE=re.compile(r'사진\s*속|사진에서|(?:표면|외형|형태).{0,12}(?:보입니다|보여요|인상)|분석\s*결과|유사도|가게\s*이름으로|눈으로\s*먼저\s*골라')
CLAIM_REVIEW=re.compile(r'장인|전문|정통|노하우|전통|단골|명성|철학|바삭|쫄깃|촉촉|부드러|고소|풍미')
SOFT_LENGTHS={'headline':24,'body':40,'cta':14}  # Advisory non-fact characters; not template limits.


def review_ad_copy(variants, ad_goal='menu_promotion', *, profile=None, draft=None):
    warnings=[]
    headlines=set()
    bodies=set()
    for variant in variants:
        cta=variant.ad_copy.cta
        if profile=='v8':
            warnings.extend(review_v8(variant,ad_goal,draft))
        else:
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


def review_v8(variant,goal,draft):
    """Small explainable review signals, not a semantic judge or retry trigger.

    Legacy fact validation remains the rejection boundary. These cues can miss
    paraphrases or flag legitimate prose; never rewrite or spend another call.
    """
    warnings=[];values=variant.ad_copy.model_dump();cta=values['cta']
    if cta:
        if re.search(r'볼까\??$',cta):warnings.append('COPY_CTA_STYLE_REVIEW')
        order=bool(ORDER_ACTION.search(cta));visit=bool(VISIT_ACTION.search(cta))
        if ((goal=='menu_promotion' and (order or visit))
            or (goal=='store_visit' and not visit and (order or MENU_ACTION.search(cta) or SERVICE_LANGUAGE.search(cta)))
            or (goal=='order' and not order and (visit or MENU_ACTION.search(cta) or SERVICE_LANGUAGE.search(cta)))):
            warnings.append('COPY_GOAL_REVIEW')
    facts=draft.facts.model_dump() if draft is not None else {}
    supplied=[facts.get(k) for k in ('store_name','product_name','price_text') if facts.get(k)]
    evidence='\n'.join([*supplied,(draft.product_features or '') if draft is not None else ''])
    if any(len(fact)>=2 and sum(text.count(fact) for text in values.values())>1 for fact in supplied):
        warnings.append('COPY_FACT_REPETITION_REVIEW')
    for field,text in values.items():
        remaining=text
        for fact in sorted(supplied,key=len,reverse=True):remaining=remaining.replace(fact,'')
        if len(remaining)>SOFT_LENGTHS[field]:warnings.append('COPY_LENGTH_REVIEW')
        if ANALYSIS_STYLE.search(remaining):warnings.append('COPY_ANALYSIS_STYLE_REVIEW')
        if any(m.group() not in evidence for m in CLAIM_REVIEW.finditer(remaining)):
            warnings.append('COPY_CLAIM_REVIEW')
    return warnings
