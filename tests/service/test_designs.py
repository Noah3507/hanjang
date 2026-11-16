"""v3 service contract tests with explicit fake rendering; real Chromium separate."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import pytest
from app.schemas.designs import DesignRequest,DesignSnapshot
from app.schemas.upload import InputDraft
from app.services.uploads import UploadError,now
from app.services.render_execution import RenderFailure
from app.services.template_v3 import TemplateInput
from test_rendering import service, fake_render


def fake_v3(data,photo,ids):
    d=InputDraft.model_validate({'facts':{'store_name':data.store_name,'product_name':data.product_name,'price_text':data.price_text},'mood':'warm'})
    copies=SimpleNamespace(variants=[SimpleNamespace(strategy=t.split('_')[0],ad_copy=SimpleNamespace(model_dump=lambda:{'headline':data.headline,'body':data.body,'cta':data.cta})) for t in ids])
    return [dict(row,template_id=t) for row,t in zip(fake_render(d,copies,photo),ids)]


@pytest.fixture
def designs(service):
    app,c,h,m,b,body,raw=service
    app.state.design_store.executor=fake_v3
    assert c.post(b+'/rendering',headers=h,json=body).status_code==202
    r=c.get(b+'/rendering',headers=h).json()
    create={'expected_render_revision':r['revision'],'expected_source_asset_id':r['source_asset_id'],'expected_copy_key':r['copy_key']}
    return app,c,h,m,b,create,r


def generate(d,strategy='price'):
    app,c,h,m,b,body,r=d
    p=b+'/designs/'+strategy
    assert c.post(p,headers=h,json=body).status_code==202
    state=c.get(p,headers=h).json()
    assert state['status']=='completed',state
    return p,state


def snap(s):return {'expected_revision':s['revision'],'expected_snapshot':s['snapshot']}


def test_four_same_strategy_identity_cache_and_v2_preserved(designs):
    app,c,h,m,b,body,v2=designs
    p,s=generate(designs)
    assert {x['strategy'] for x in s['candidates']}=={'price'}
    assert {x['template_id'] for x in s['candidates']}=={'price_'+x for x in 'abcd'}
    assert len({x['candidate_id'] for x in s['candidates']})==4
    assert len({x['png']['asset_id'] for x in s['candidates']})==4
    assert c.get(b+'/rendering',headers=h).json()==v2
    c.post(p,headers=h,json=body)
    assert c.get(p,headers=h).json()['snapshot']==s['snapshot']
    for x in s['candidates']:
        assert c.get(x['png']['url'],headers=h).status_code==200
    _,other=generate(designs,'brand')
    assert c.get(p,headers=h).json()['snapshot']==s['snapshot']
    assert not {x['candidate_id'] for x in s['candidates']}&{x['candidate_id'] for x in other['candidates']}


def test_edit_price_revision_stale_rank_download_and_original_facts(designs):
    app,c,h,m,b,body,v2=designs;p,s=generate(designs);first=s['candidates'][0]
    ranked=c.post(p+'/ranking',headers=h,json=snap(s)).json()
    assert ranked['ranking']['source']=='mock'
    path=p+'/candidates/'+first['candidate_id']
    change={**snap(s),'expected_asset_id':first['png']['asset_id'],'copy':{**first['copy'],'headline':'사용자가 수정한 제목'},'price_text':'12,000원'}
    assert c.patch(path,headers=h,json=change).status_code==202
    n=c.get(p,headers=h).json();assert n['revision']==2 and n['ranking'] is None
    updated=n['candidates'][0]
    assert updated['candidate_id']==first['candidate_id'] and updated['png']['asset_id']!=first['png']['asset_id']
    assert updated['copy']['headline']=='사용자가 수정한 제목' and updated['facts']['price_text']=='12,000원'
    assert updated['edit_revision']==1 and updated['original_price_text']==first['facts']['price_text']
    assert [x['png']['asset_id'] for x in n['candidates'][1:]]==[x['png']['asset_id'] for x in s['candidates'][1:]]
    assert c.get(b+'/rendering',headers=h).json()==v2
    assert c.patch(path,headers=h,json=change).status_code==409
    old=c.get(path+'/download',headers=h,params={'format':'png',**snap(s)});assert old.status_code==409
    new=c.get(path+'/download',headers=h,params={'format':'png',**snap(n)});assert new.status_code==200
    assert new.content==c.get(updated['png']['url'],headers=h).content
    app.state.design_store.pdf=lambda png:b'%PDF-test-only'
    assert c.get(path+'/download',headers=h,params={'format':'pdf',**snap(n)}).content==b'%PDF-test-only'
    assert c.get(p+'/diagnostics',headers=h).json()['revision']==2


def test_auth_cross_owner_invalid_strategy_expiry_and_tampered_file(designs):
    app,c,h,m,b,body,_=designs;p,s=generate(designs)
    assert c.get(p).status_code==401
    other={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
    assert c.get(p,headers=other).status_code==404
    assert c.get(b+'/designs/nope',headers=h).status_code==422
    rec=app.state.upload_store.records[m['job_id']]
    rec.derived[s['candidates'][0]['png']['asset_id']].write_bytes(b'broken-test-file')
    assert c.get(p,headers=h).status_code==409
    rec.upload.expires_at=now()-timedelta(seconds=1)
    assert c.get(p,headers=h).status_code==410


def test_inflight_source_change_and_render_failure_retries(designs):
    app,c,h,m,b,body,v2=designs;store=app.state.design_store
    def bad(*args):raise RenderFailure('RENDER_LAYOUT_OVERFLOW')
    store.executor=bad
    c.post(b+'/designs/price',headers=h,json=body)
    assert c.get(b+'/designs/price',headers=h).json()['status']=='failed'
    store.executor=fake_v3;p,s=generate(designs)
    first=s['candidates'][0];change={**snap(s),'expected_asset_id':first['png']['asset_id'],'copy':{**first['copy'],'headline':'실패할 수정'},'price_text':first['facts']['price_text']}
    store.executor=bad;c.patch(p+'/candidates/'+first['candidate_id'],headers=h,json=change)
    n=c.get(p,headers=h).json();assert n['snapshot']==s['snapshot'] and n['status']=='completed' and n['error']
    store.executor=fake_v3
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    create=DesignRequest.model_validate(body)
    pending,task=store.start(owner,m['job_id'],'visual',create)
    with pytest.raises(UploadError) as e:store.start(owner,m['job_id'],'brand',create)
    assert e.value.code=='RENDER_BUSY'
    draft=app.state.upload_store.records[m['job_id']].draft.model_copy(deep=True)
    draft.product_features='새로운 입력'
    app.state.upload_store.save_draft(owner,m['job_id'],draft)
    store.finish(owner,m['job_id'],task)
    n=store.get(owner,m['job_id'],'visual');assert n.status=='failed' and not n.is_current
    assert not store.renders.active


def test_rank_failure_never_mock_fallback_and_late_result_stale(designs):
    app,c,h,m,b,body,v2=designs;p,s=generate(designs);store=app.state.design_store
    class Fail:
        mode='model'
        def rank_snapshot(self,*args):raise RuntimeError('sensitive internals must not leak')
    store.ranker=Fail()
    n=c.post(p+'/ranking',headers=h,json=snap(s)).json()
    assert n['ranking'] is None and n['ranking_status']=='failed'
    assert 'sensitive' not in str(n)
    class Late:
        mode='model'
        def rank_snapshot(self,candidates,revision,pngs):
            from app.schemas.ranking import Ranking
            from app.ml_adapter.mock_ranker import ordered_items
            rec=app.state.upload_store.records[m['job_id']];rec.draft.product_features='changed during inference'
            return Ranking(source='model',model_version='synthetic-model-test',feature_version='synthetic-features',
                revision=revision,items=ordered_items([(x.candidate_id,float(i)) for i,x in enumerate(candidates)]))
    store.ranker=Late()
    assert c.post(p+'/ranking',headers=h,json=snap(s)).status_code==409
    assert c.get(p,headers=h).json()['ranking'] is None


@pytest.mark.parametrize('change',[
 {'price_text':'10,500원','original_price':'15,000원','discount_text':'90%'},
 {'price_text':'$10','original_price':'20원','discount_text':'50%'},
 {'discount_text':'30%'}, {'period_text':'2026.11.20–2026.11.16'},
 {'original_price':'10,000원'},
])
def test_invalid_claims(change):
    data=TemplateInput('상점','상품','10,500원','제목')
    with pytest.raises(RenderFailure):replace(data,**change).validate()


def test_claim_rounding_and_hidden_price_preserve_raw():
    d=TemplateInput('상점','상품',' 10,500원 ','제목',original_price='15,000원',discount_text='30%')
    d.validate();assert d.price_text==' 10,500원 '
    replace(d,price_text='가격 비공개',original_price='',discount_text='').validate()
    replace(d,price_text='',original_price='',discount_text='').validate()
    replace(d,original_price='11,700원',discount_text='10%',period_text='2026.11.16–11.20').validate()
