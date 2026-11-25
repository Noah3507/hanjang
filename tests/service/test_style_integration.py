"""A-owned analysis/style wiring and stale regressions. Fake PNGs here; Chromium separate."""
from dataclasses import replace
from types import SimpleNamespace
import json
import os
import pytest
from app.schemas.analysis import AnalysisResponse, ClipResult, Cue, Palette
from app.services.analysis_kind import product_kind_hint
from app.services import design_style
from test_rendering import service
from test_designs import designs, generate, snap, fake_v3

def clip(scores):
    return ClipResult(status='available',cues=[Cue(category=cat,candidate_id=label,label='추정',similarity=score)
                                             for cat,label,score in scores])

def test_kind_hint_uses_category_ids_and_actual_scores_only():
    c=clip([('category','food',.27),('category','dessert',.24),('appearance','round',.99),('impression','bright',.95)])
    h=product_kind_hint(c)
    assert h.label=='food' and h.similarity==.27 and h.margin==pytest.approx(.03)
    for bad in [ClipResult(),clip([('category','food',.3)]),clip([('category','food',.3),('category','drink',.3)]),
                clip([('category','food',.3),('category','food',.2)]),
                ClipResult.model_construct(status='available',cues=[SimpleNamespace(category='category',candidate_id='food',similarity=float('nan'))])]:
        assert product_kind_hint(bad) is None

def analysis(designs,color='#DA7134',status='completed',source=None):
    app,c,h,m,b,body,_=designs
    palette=Palette.model_validate_json('{"status":"available","colors":[{"hex":"'+color+'","rgb":'+str(list(bytes.fromhex(color[1:])))+',"proportion":1}],"sampled_pixels":10}')
    rec=app.state.upload_store.records[m['job_id']]
    rec.analyses[m['asset_id']]=AnalysisResponse(job_id=m['job_id'],status=status,status_url=b+'/photo-analysis',
        source_asset_id=source or m['asset_id'],photo_source='original',is_current=True,expires_at=rec.upload.expires_at,palette=palette)
    return rec

def test_cached_analysis_get_additive_hint_and_no_new_inference(designs):
    app,c,h,m,b,_,_=designs;rec=analysis(designs)
    rec.analyses[m['asset_id']].clip=clip([('category','drink',.35),('category','food',.21)])
    app.state.analysis_store.executor=lambda _:pytest.fail('No extra CLIP inference')
    result=c.get(b+'/photo-analysis',headers=h).json()
    assert result['product_kind_hint']['label']=='drink'
    assert result['product_kind_hint']['margin']==pytest.approx(.14)
    from app.services.design_style_context import resolve_bundle
    draft=rec.draft.model_copy(deep=True);draft.facts.product_name='분류미상'
    page=resolve_bundle(rec,SimpleNamespace(asset_id=m['asset_id']),draft,['price_a']).page('price_a')
    assert page.inputs.kind_hint=='drink' and page.inputs.kind_hint_margin==pytest.approx(.14)
    assert page.kind=='drink' and page.kind_source=='clip'

@pytest.mark.parametrize('state,source',[('failed',None),('processing',None),('completed','0'*32)])
def test_bad_or_stale_analysis_is_empty_but_name_style_survives(designs,state,source):
    app,c,h,m,b,body,_=designs;analysis(designs,status=state,source=source)
    p,s=generate(designs)
    for v in s['style_snapshot'].values():
        assert v['inputs']['palette']==[] and v['inputs']['kind_hint'] is None
        assert v['kind_source']=='name' and v['variables']

def test_palette_transition_invalidates_rank_edit_download_and_rebuilds(designs):
    app,c,h,m,b,body,_=designs;p,old=generate(designs)
    c.post(p+'/ranking',headers=h,json=snap(old))
    analysis(designs)
    stale=c.get(p,headers=h).json();assert not stale['is_current'] and stale['ranking'] is None
    first=old['candidates'][0];url=p+'/candidates/'+first['candidate_id']
    assert c.get(url+'/download',headers=h,params={'format':'png',**snap(old)}).status_code==409
    assert c.patch(url,headers=h,json={**snap(old),'expected_asset_id':first['png']['asset_id'],'copy':first['copy'],'price_text':first['facts']['price_text']}).status_code==409
    p,new=generate(designs);assert new['snapshot']!=old['snapshot']
    assert new['style_snapshot']['price_a']['inputs']['palette']==[['#DA7134',1.0]]
    analysis(designs,color='#59AB42');assert not c.get(p,headers=h).json()['is_current']

@pytest.mark.parametrize('change',['version','variables'])
def test_style_implementation_change_fences_existing_sets(designs,monkeypatch,change):
    app,c,h,m,b,body,_=designs;p,s=generate(designs)
    if change=='version':monkeypatch.setattr(design_style,'STYLE_VERSION','synthetic-next-version')
    else:
        original=design_style.resolve_style
        monkeypatch.setattr(design_style,'resolve_style',lambda d:replace(original(d),variables={**original(d).variables,'decor':'#123456'}))
    assert not c.get(p,headers=h).json()['is_current']

def test_style_change_during_render_never_publishes_new_style_as_old(designs):
    app,c,h,m,b,body,_=designs;store=app.state.design_store
    seen=[]
    def changing(data,raw,ids):
        seen.append(data.style_context.snapshot(ids));analysis(designs)
        return fake_v3(data,raw,ids)
    store.executor=changing
    c.post(b+'/designs/price',headers=h,json=body)
    s=c.get(b+'/designs/price',headers=h).json()
    assert s['status']=='failed' and not s['is_current'] and not s['candidates']
    assert s['style_snapshot']==json.loads(json.dumps(seen[0]))  # captured style, JSON tuple encoding only

def test_single_edit_keeps_style_other_assets_and_never_runs_clip_or_copy(designs):
    app,c,h,m,b,body,_=designs;analysis(designs);p,s=generate(designs)
    app.state.analysis_store.executor=lambda _:pytest.fail('Unexpected CLIP')
    app.state.copy_store.provider.generate=lambda _:pytest.fail('Unexpected LLM')
    first=s['candidates'][0];captured=[];store=app.state.design_store
    def editing(data,raw,ids):captured.append((data.style_context.snapshot(ids),ids));return fake_v3(data,raw,ids)
    store.executor=editing
    c.post(p+'/ranking',headers=h,json=snap(s))
    change={**snap(s),'expected_asset_id':first['png']['asset_id'],'copy':{**first['copy'],'headline':'직접 수정한 제목'},'price_text':'12,000원'}
    assert c.patch(p+'/candidates/'+first['candidate_id'],headers=h,json=change).status_code==202
    n=c.get(p,headers=h).json()
    assert n['style_snapshot']==s['style_snapshot'] and n['ranking'] is None
    assert captured[0][1]==[first['template_id']]
    assert [x['png']['asset_id'] for x in n['candidates'][1:]]==[x['png']['asset_id'] for x in s['candidates'][1:]]
    reranked=c.post(p+'/ranking',headers=h,json=snap(n)).json()
    assert reranked['ranking']['revision']==2
    assert {v['candidate_id'] for v in reranked['ranking']['items']}=={v['candidate_id'] for v in n['candidates']}

@pytest.mark.parametrize('field',['mood','product_name'])
def test_changed_user_style_inputs_make_existing_designs_stale(designs,field):
    app,c,h,m,b,body,_=designs;p,s=generate(designs)
    rec=app.state.upload_store.records[m['job_id']]
    draft=rec.draft.model_copy(deep=True)
    if field=='mood':draft.mood='premium'
    else:draft.facts.product_name='샐러드'
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    app.state.upload_store.save_draft(owner,m['job_id'],draft)
    assert not c.get(p,headers=h).json()['is_current']

def test_analysis_change_during_rank_cannot_publish_late_scores(designs):
    from app.schemas.ranking import Ranking
    from app.ml_adapter.mock_ranker import ordered_items
    app,c,h,m,b,body,_=designs;p,s=generate(designs)
    class Late:
        mode='model'
        def rank_snapshot(self,candidates,revision,pngs):
            analysis(designs)
            return Ranking(source='model',model_version='synthetic-test-only',feature_version='synthetic',revision=revision,
                items=ordered_items([(v.candidate_id,float(i)) for i,v in enumerate(candidates)]))
    app.state.design_store.ranker=Late()
    assert c.post(p+'/ranking',headers=h,json=snap(s)).status_code==409
    current=c.get(p,headers=h).json()
    assert not current['is_current'] and current['ranking'] is None

@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in; technical fixture only')
def test_chromium_empty_css_pixel_identity_and_separate_template_styles():
    from io import BytesIO
    from PIL import Image,ImageChops
    from app.services.design_style_context import resolve_bundle
    from app.services.template_v3 import render_templates,TemplateInput
    from test_template_v3 import photo
    record=SimpleNamespace(analyses={});asset=SimpleNamespace(asset_id='synthetic-fixture')
    draft=SimpleNamespace(mood='warm',facts=SimpleNamespace(product_name='분류미상'))
    d=TemplateInput('검증 상점','분류미상','7,000원','오늘의 선택','짧은 본문','메뉴 보기')
    bundle=resolve_bundle(record,asset,draft,['price_a'])
    assert bundle.page('price_a').css()==''
    original=render_templates(d,photo(),['price_a'])[0]
    empty=render_templates(replace(d,style_context=bundle),photo(),['price_a'])[0]
    assert ImageChops.difference(Image.open(BytesIO(original['png'])),Image.open(BytesIO(empty['png']))).getbbox() is None
    draft.facts.product_name='에스프레소';ids=['price_'+c for c in 'abcd']
    bundle=resolve_bundle(record,asset,draft,ids)
    rows=render_templates(replace(d,product_name='에스프레소',style_context=bundle),photo(),ids)
    assert len({bundle.page(t).css() for t in ids})>1
    for row in rows:
        assert list(row['style_snapshot'])==[row['template_id']]
        assert row['style_snapshot'][row['template_id']]['variables']==bundle.page(row['template_id']).variables
        assert all(not t['overflow'] for t in row['measurement']['text'])
