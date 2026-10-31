"""Measurable layout risks, not preference, OCR, visual attention or certification."""
import math
from app.schemas.diagnostics import RuleResult,CandidateDiagnostics
from app.services.diagnostics_evidence import EVIDENCE_VERSION

RULES_VERSION='readability-rules-v1'
SMALL_FONT_PX=36.0  # Tunable initial service heuristic, not a universal standard.
DENSITY_LIMIT=.40  # Union of text BLOCK rectangles, not glyph ink or a score.
WIDTH,HEIGHT=1080,1350

def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def rect(v):
    if not isinstance(v,dict):return None
    a=[v.get(k) for k in ('x','y','width','height')]
    if not all(number(n) for n in a) or a[2]<=0 or a[3]<=0:return None
    x,y,w,h=a
    return (x,y,w,h) if number(x+w) and number(y+h) else None
def area_intersection(a,b):
    w=min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]);h=min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1])
    return w*h if w>1 and h>1 else 0.
def union_area(rectangles):
    # Sweep line; no duplicate area. Clip to the actual canvas.
    rs=[]
    for x,y,w,h in rectangles:
        l,r=max(0,x),min(WIDTH,x+w);t,b=max(0,y),min(HEIGHT,y+h)
        if r>l and b>t:rs.append((l,t,r,b))
    xs=sorted({x for l,t,r,b in rs for x in (l,r)})
    total=0.
    for l,r in zip(xs,xs[1:]):
        intervals=sorted((t,b) for x,t,z,b in rs if x<r and z>l)
        length=0.;end=None
        for t,b in intervals:
            length+=b-t if end is None or t>end else max(0,b-end)
            end=b if end is None else max(end,b)
        total+=(r-l)*length
    return total
def color(v):return isinstance(v,list) and len(v)==3 and all(isinstance(n,int) and not isinstance(n,bool) and 0<=n<=255 for n in v)
def contrast(foreground,background):
    if not color(foreground) or not color(background):raise ValueError('Invalid colors')
    def luminance(rgb):
        s=[v/255 for v in rgb]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in s]
        return sum(w*v for w,v in zip((.2126,.7152,.0722),linear))
    a,b=sorted((luminance(foreground),luminance(background)))
    return (b+.05)/(a+.05)
def summary(statuses):
    if not statuses:return 'unavailable','unavailable'
    unknown=statuses.count('unavailable')
    coverage='unavailable' if unknown==len(statuses) else 'partial' if unknown else 'complete'
    status=next((s for s in ('problem','caution','unavailable') if s in statuses),'normal')
    return status,coverage
def rule(rule_id,statuses,value,unit,criterion,explanation,action):
    status,coverage=summary(statuses)
    return RuleResult(rule_id=rule_id,status=status,coverage=coverage,measured_value=value,unit=unit,
                      criterion=criterion,explanation=explanation,action=action)

def fonts(texts):
    items=[]
    for t in texts:
        value=t.get('font_size_px');valid=number(value) and value>0
        items.append({'field':t.get('field','unknown'),'value':value if valid else None,
                      'status':'unavailable' if not valid else 'caution' if value<SMALL_FONT_PX else 'normal'})
    values=[i['value'] for i in items if i['value'] is not None]
    return rule('font_size',[i['status'] for i in items],{'minimum':min(values) if values else None,'items':items},'PNG px (현재 CSS px와 1:1)',
        f'{SMALL_FONT_PX:g} PNG px 미만 주의 · 조정 가능한 서비스 휴리스틱',
        '캔버스 글꼴 크기이며 실제 모바일 표시나 인쇄 가독성을 보장하지 않습니다.',
        '작은 글자가 있으면 문구를 줄여 재렌더링하고 실제 표시 크기로 확인해 주세요. 자유 글꼴 편집은 지원하지 않습니다.')

def contrast_rule(texts,measurement,png_hash):
    raw=measurement.get('text') if isinstance(measurement,dict) else None
    raw=raw if isinstance(raw,list) else []
    items=[]
    for t in texts:
        item={'field':t.get('field','unknown'),'value':None,'threshold':None,'status':'unavailable'}
        candidates=[x for x in raw if isinstance(x,dict) and x.get('field')==t.get('field')]
        if len(candidates)==1:
            m=candidates[0];e=m.get('contrast_evidence',{})
            match=all(m.get(k)==t.get(k) for k in ('text','x','y','width','height','font_size_px','font_weight'))
            fg=e.get('foreground_rgb') if isinstance(e,dict) else None
            if (match and m.get('contrast_eligible') is True and isinstance(e,dict) and e.get('version')==EVIDENCE_VERSION and e.get('status')=='verified'
                and e.get('png_sha256')==png_hash and color(fg) and color(e.get('background_rgb'))
                and '#'+''.join(f'{n:02X}' for n in fg)==str(t.get('foreground','')).upper()):
                item['value']=contrast(fg,e['background_rgb'])
                size,weight=t.get('font_size_px'),t.get('font_weight')
                if number(size) and size>0 and number(weight):
                    large=size>=24 or size>=14*96/72 and weight>=700
                    item['threshold']=3. if large else 4.5
                    item['status']='normal' if item['value']>=item['threshold'] else 'problem'
        items.append(item)
    ratios=[i['value'] for i in items if i['value'] is not None]
    return rule('contrast',[i['status'] for i in items],{'minimum':min(ratios) if ratios else None,'items':items},'contrast ratio',
        'WCAG식 참고: 일반 4.5:1 / 큰 글자 3:1 (24 CSS px 또는 18.67px·700 이상)',
        '실제 배경 캡처로 확인된 단색 픽셀과 전경만 계산합니다. 이미지·그라데이션·합성 불확실 항목은 측정 불가이며 접근성 인증이 아닙니다.',
        '미리보기에서 확인해 주세요. 현재 자유 색상·배경 편집과 자동 보정은 지원하지 않습니다.')

def layout(texts,product):
    rs=[rect(t) for t in texts];p=rect(product);statuses=[];outside=[];overflow=[];missing=[];pairs=[];images=[]
    for i,(t,r) in enumerate(zip(texts,rs)):
        field=t.get('field','unknown')
        if r is None:missing.append(field);statuses.append('unavailable');continue
        x,y,w,h=r
        if x<0 or y<0 or x+w>WIDTH or y+h>HEIGHT:outside.append(field);statuses.append('problem')
        else:statuses.append('normal')
        if not isinstance(t.get('overflow'),bool):missing.append(field+' overflow');statuses.append('unavailable')
        elif t['overflow']:overflow.append(field);statuses.append('caution')
        for j,b in enumerate(rs[i+1:],i+1):
            if b and area_intersection(r,b):pairs.append({'fields':[field,texts[j].get('field','unknown')],'area':area_intersection(r,b)});statuses.append('caution')
        if p and area_intersection(r,p):images.append({'field':field,'area':area_intersection(r,p)});statuses.append('caution')
    if p is None:missing.append('product_bbox');statuses.append('unavailable')
    return rule('layout',statuses,{'out_of_bounds':outside,'overflow':overflow,'text_intersections':pairs,'image_intersections':images,'missing':missing},'PNG px / px²',
        '캔버스 1080×1350 이탈은 문제, 1px 초과 bbox 교차·DOM overflow는 주의',
        'bbox 겹침은 글자 획이나 상품 가림의 확정 판정이 아닙니다. 투명 이미지 영역·의도적인 배치를 구분하지 못합니다.',
        '문구를 줄여 재렌더링하고 확대 화면을 확인해 주세요. 명확한 영역 이탈과 배치 위험을 구분합니다.')

def density(texts):
    rs=[rect(t) for t in texts];valid=[r for r in rs if r is not None]
    value=union_area(valid)/(WIDTH*HEIGHT) if valid else None
    missing=len(rs)-len(valid)
    statuses=[] if value is None else ['caution' if value>DENSITY_LIMIT else 'normal']
    if missing:statuses.append('unavailable')
    counts={t.get('field','unknown'):len(t['text']) for t in texts if t.get('field') in ('headline','body','cta') and isinstance(t.get('text'),str)}
    return rule('density',statuses,{'ratio':value,'missing_boxes':missing,'copy_characters':counts},'text block area / canvas',
        f'중복을 제외한 bbox 합집합이 {DENSITY_LIMIT*100:g}% 초과이면 주의 · 서비스 휴리스틱',
        '텍스트 블록 면적이며 실제 글자 잉크·정보 이해도·가독성 점수가 아닙니다. 누락 시 확인된 영역만 표시합니다.',
        '제목·본문·CTA의 역할을 살려 문구를 줄여 보세요. 길이만으로 가독성을 단정하지 않습니다.')

def analyze(candidate,measurement,png_hash):
    renderer=candidate.get('renderer',{})
    renderer=renderer if isinstance(renderer,dict) else {}
    texts=renderer.get('text_boxes')
    texts=texts if isinstance(texts,list) else []
    texts=[t if isinstance(t,dict) else {'field':'unknown'} for t in texts]
    methods=[('contrast',lambda:contrast_rule(texts,measurement,png_hash)),('font_size',lambda:fonts(texts)),
             ('layout',lambda:layout(texts,renderer.get('product_bbox'))),('density',lambda:density(texts))]
    results=[]
    for name,method in methods:
        try:results.append(method())
        except Exception:
            results.append(rule(name,[],None,'','측정 근거 필요','이 항목의 계산 근거를 확인하지 못했습니다.','다른 유효한 측정값과 미리보기를 확인해 주세요.'))
    coverages=[r.coverage for r in results]
    coverage='complete' if all(c=='complete' for c in coverages) else 'unavailable' if all(c=='unavailable' for c in coverages) else 'partial'
    return CandidateDiagnostics(candidate_id=candidate['candidate_id'],strategy=candidate['strategy'],asset_id=candidate['png']['asset_id'],coverage=coverage,rules=results)
