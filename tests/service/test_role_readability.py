"""Team role policy at the v2 and actual v3 adapter boundaries; no paid calls."""
from copy import deepcopy
import pytest
from app.services import diagnostics_engine as e
from app.services.template_v3 import measured_diagnostics
from test_diagnostics import candidate, rules, prepared, request, service
from test_designs import designs, generate, snap


FIELDS={'headline':36,'price_text':36,'product_name':32,'body':28,'cta':28,'store_name':28,'address':24,
        'instagram':24,'discount_text':24,'original_price':24,'promotion_text':24,'period_text':24}


@pytest.mark.parametrize('field,threshold',FIELDS.items())
@pytest.mark.parametrize('delta,status',[(0,'normal'),(-.000001,'caution'),(1,'normal')])
def test_role_final_font_boundary(field,threshold,delta,status):
    text={'field':field,'font_size_px':threshold+delta,'initial_font_size_px':48.,'size_ratio':(threshold+delta)/48}
    item=e.fonts([text]).measured_value['items'][0]
    assert (item['threshold'],item['value'],item['status'])==(threshold,threshold+delta,status)
    assert item['initial_font_size_px']==48 and item['size_ratio']==text['size_ratio']


@pytest.mark.parametrize('tid,threshold',[('visual_a',24),('visual_c',24),('visual_d',24),
    ('visual_b',28),('emotional_a',28),('brand_a',28),('price_a',28),(None,28),('visual_a-extra',28)])
def test_only_exact_body_template_exceptions(tid,threshold):
    items=e.fonts([{'field':'body','font_size_px':25},{'field':'headline','font_size_px':25}],template_id=tid).measured_value['items']
    assert items[0]['threshold']==threshold
    assert items[0]['status']==('normal' if threshold==24 else 'caution')
    assert items[1]['threshold']==36 and items[1]['status']=='caution'
    assert e.fonts([{'field':'body','font_size_px':threshold}],template_id=tid).status=='normal'


@pytest.mark.parametrize('text',[{'field':'mystery','font_size_px':80},{'font_size_px':80},
    {'field':'body'},{'field':'body','font_size_px':float('nan')},{'field':'body','font_size_px':0}])
def test_unknown_role_or_missing_metrics_unavailable(text):
    item=e.fonts([text]).measured_value['items'][0]
    assert item['status']=='unavailable'
    if text.get('field') not in e.FIELD_ROLES:assert item['role']=='unknown' and item['threshold'] is None


def measurement(tid):
    t=deepcopy(candidate()['renderer']['text_boxes'][0])
    t.update(field='body',font_size_px=25,initial_font_size_px=32,size_ratio=25/32,
             foreground='rgb(0, 0, 0)',background='rgba(0, 0, 0, 0)')
    return {'template_id':tid,'text':[t],'product':{'x':20,'y':500,'width':200,'height':200}}


@pytest.mark.parametrize('tid,threshold',[('visual_a',24),('visual_b',28),('visual_c',24),('visual_d',24)])
def test_v3_adapter_identity_ratio_and_other_rules(tid,threshold):
    m=measurement(tid);m['text'][0]['overflow']=True
    result=measured_diagnostics('c','a','visual',m,'hash',template_id=tid)
    rs={r['rule_id']:r for r in result['rules']}
    font=rs['font_size']['measured_value'];item=font['items'][0]
    assert font['template_id']==tid and font['policy_version']==e.RULES_VERSION
    assert item['threshold']==threshold and item['size_ratio']==25/32
    assert rs['layout']['status']=='caution' and rs['contrast']['status']=='unavailable'


def test_v3_does_not_guess_or_accept_mismatched_template():
    m=measurement('visual_a')
    with pytest.raises(ValueError):measured_diagnostics('c','a','visual',m,'h',template_id='visual_b')
    with pytest.raises(ValueError):measured_diagnostics('c','a','price',m,'h',template_id='visual_a')
    m.pop('template_id')
    result=measured_diagnostics('c','a','visual',m,'h')
    assert next(r for r in result['rules'] if r['rule_id']=='font_size')['measured_value']['items'][0]['threshold']==28
    c=candidate();c['strategy']='visual';c['renderer']['text_boxes'][0].update(field='body',font_size_px=25)
    assert rules(c,measurement('visual_a'))['font_size'].measured_value['items'][0]['threshold']==28 # v2


@pytest.mark.parametrize('change',['version','roles','exceptions'])
def test_v2_policy_cache_only_diagnostics_changes(service,monkeypatch,change):
    app,c,h,m,b,_,_=service;r,_=prepared(service)
    c.post(b+'/ranking',headers=h,json={'expected_render_revision':r['revision'],'expected_candidate_ids':[x['candidate_id'] for x in r['candidates']]})
    rank=c.get(b+'/ranking',headers=h).json()
    c.post(b+'/diagnostics',headers=h,json=request(r))
    if change=='version':monkeypatch.setattr(e,'RULES_VERSION','test-next-policy')
    elif change=='roles':monkeypatch.setattr(e,'ROLE_THRESHOLDS',{**e.ROLE_THRESHOLDS,'body':30})
    else:monkeypatch.setattr(e,'BODY_TEMPLATE_EXCEPTIONS',{'visual_a':23})
    assert not c.get(b+'/diagnostics',headers=h).json()['is_current']
    result=c.post(b+'/diagnostics',headers=h,json=request(r)).json()
    assert result['is_current'] and result['rules_version']==e.RULES_VERSION
    assert c.get(b+'/rendering',headers=h).json()==r and c.get(b+'/ranking',headers=h).json()==rank


def test_v3_cached_evidence_reevaluates_without_render_rank_copy_changes(designs,monkeypatch):
    app,c,h,m,b,body,v2=designs;p,s=generate(designs,'visual')
    ranked=c.post(p+'/ranking',headers=h,json=snap(s)).json()
    record=app.state.upload_store.records[m['job_id']];entry=record.design_sets['visual']
    for candidate_data in entry.response.candidates:
        # Legacy measurement without template ID is safely bound by the stored candidate.
        entry.measurements[candidate_data.candidate_id]['text'][0].update(field='body',font_size_px=25)
    monkeypatch.setattr(e,'RULES_VERSION','test-next-policy')
    def forbidden(*a,**kw):raise AssertionError('Diagnostics must not regenerate')
    app.state.design_store.executor=forbidden;app.state.design_store.ranker.rank_snapshot=forbidden
    app.state.copy_store.provider.generate=forbidden
    original_copy=c.get(b+'/copy-generation',headers=h).json()
    result=c.get(p+'/diagnostics',headers=h).json()
    latest=c.get(p,headers=h).json()
    assert latest['ranking']==ranked['ranking'] and latest['candidates']==ranked['candidates']
    assert latest['snapshot']==ranked['snapshot'] and latest['revision']==ranked['revision']
    assert c.post(p,headers=h,json=body).status_code==202
    assert c.get(b+'/rendering',headers=h).json()==v2
    assert c.get(b+'/copy-generation',headers=h).json()==original_copy
    for cd,diag in zip(latest['candidates'],result['results']):
        value=next(x for x in diag['rules'] if x['rule_id']=='font_size')['measured_value']
        assert value['template_id']==cd['template_id'] and value['policy_version']=='test-next-policy'
        assert value['items'][0]['threshold']==(28 if cd['template_id']=='visual_b' else 24)
    first=latest['candidates'][0]
    assert c.get(p+'/candidates/'+first['candidate_id']+'/download',headers=h,params={'format':'png',**snap(ranked)}).status_code==200
