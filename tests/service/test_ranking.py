"""Real local API/store + fake PNG renderer; no ML, network or paid providers."""
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jsonschema import validate
from pydantic import ValidationError
from app.ml_adapter.mock_ranker import MockRanker, ordered_items
from app.schemas.ranking import Ranking, RankingRequest
from app.services.uploads import now, UploadError
from test_rendering import service, draft, png


def rendered(service):
    app, c, h, m, b, body, _ = service
    assert c.post(b+'/rendering', headers=h, json=body).status_code == 202
    r = c.get(b+'/rendering', headers=h).json()
    request = {'expected_render_revision': r['revision'], 'expected_candidate_ids': [v['candidate_id'] for v in r['candidates']]}
    return app, c, h, m, b, request, r


def test_mock_contract_fixture_determinism_and_ties():
    fixture = json.loads(Path('tests/fixtures/contracts/ranking.mock.json').read_text())
    assert Ranking.model_validate(fixture).model_dump() == fixture
    strategies = ['emotional', 'price', 'visual', 'brand']
    candidates = [SimpleNamespace(candidate_id='c_'+s, strategy=s, revision=1) for s in strategies]
    result = MockRanker().rank(candidates, 1)
    assert result.model_dump() == fixture
    assert MockRanker().rank(list(reversed(candidates)), 1) == result
    ties = Ranking(source='mock', model_version='mock-v1', feature_version=None, revision=1,
        items=ordered_items([('d', .5), ('a', .5), ('c', .5), ('b', .5)]))
    assert [i.candidate_id for i in ties.items] == ['a', 'b', 'c', 'd']


@pytest.mark.parametrize('change', [lambda r:r['items'][0].update(score=float('nan')),
    lambda r:r['items'][0].update(score=float('inf')), lambda r:r['items'][0].update(rank=2),
    lambda r:r['items'][0].update(candidate_id=r['items'][1]['candidate_id']),
    lambda r:r.update(feature_version='made-up'), lambda r:r.update(model_version='real-model'),
    lambda r:r.update(pairwise={'method':'bradley_terry_sigmoid_v1','comparisons':[]})])
def test_invalid_ranking_rejected(change):
    raw = json.loads(Path('tests/fixtures/contracts/ranking.mock.json').read_text()); change(raw)
    with pytest.raises(ValidationError): Ranking.model_validate(raw)


def test_pending_completed_cache_and_private_pngs(service):
    app,c,h,m,b,_,_ = service
    assert c.get(b+'/ranking',headers=h).json()['status'] == 'pending'
    request={'expected_render_revision':1,'expected_candidate_ids':['a','b','c','d']}
    assert c.post(b+'/ranking',headers=h,json=request).status_code == 409
    app,c,h,m,b,request,r = rendered(service)
    response=c.post(b+'/ranking',headers=h,json=request)
    assert response.status_code==202 and response.headers['location']==b+'/ranking'
    assert response.headers['cache-control']=='no-store'
    final=c.get(b+'/ranking',headers=h).json()
    assert final['status']=='completed' and final['is_current'] and final['revision']==r['revision']
    ranking=final['ranking']
    validate(ranking,json.loads(Path('tests/fixtures/contracts/ranking.schema.json').read_text()))
    assert set(i['candidate_id'] for i in ranking['items'])==set(request['expected_candidate_ids'])
    assert ranking['source']=='mock' and ranking['model_version']=='mock-v1'
    assert ranking['feature_version'] is None and ranking['pairwise'] is None
    assert c.post(b+'/ranking',headers=h,json=request).json()==final
    assert c.get(b+'/rendering',headers=h).json()==r


@pytest.mark.parametrize('ids', [[], ['a']*4, ['a','b','c'], ['a','b','c','d','e']])
def test_request_count_and_duplicates(service, ids):
    _,c,h,_,b,_,_=service
    assert c.post(b+'/ranking',headers=h,json={'expected_render_revision':1,'expected_candidate_ids':ids}).status_code==422


def test_auth_owner_conflict_and_body_limit(service):
    app,c,h,m,b,request,r=rendered(service)
    other={'X-Hanjang-Session':c.post('/api/v1/sessions').json()['session_token']}
    for method in ['get','post']:
        kwargs={'json':request} if method=='post' else {}
        assert getattr(c,method)(b+'/ranking',**kwargs).status_code==401
        assert getattr(c,method)(b+'/ranking',headers=other,**kwargs).status_code==404
    assert c.post(b+'/ranking',headers=h,json={**request,'expected_render_revision':9}).status_code==409
    assert c.post(b+'/ranking',headers=h,json={**request,'expected_candidate_ids':['a','b','c','d']}).status_code==409
    assert c.post(b+'/ranking',headers=h,content=b'x'*16385).status_code==413


def test_stale_new_revision_and_old_response(service):
    app,c,h,m,b,request,r=rendered(service)
    c.post(b+'/ranking',headers=h,json=request)
    first=c.get(b+'/ranking',headers=h).json()
    changed=draft();changed['facts']['price_text']='새 가격 12,000원'
    c.put(b+'/input',headers=h,json=changed)
    old=c.get(b+'/ranking',headers=h).json()
    assert not old['is_current'] and old['ranking']==first['ranking']
    assert c.post(b+'/ranking',headers=h,json=request).status_code==409
    cb={'expected_asset_id':m['asset_id'],'expected_input':changed}
    c.post(b+'/copy-generation',headers=h,json=cb)
    copy=c.get(b+'/copy-generation',headers=h).json()
    c.post(b+'/rendering',headers=h,json={**cb,'expected_copy_key':copy['copy_key']})
    new=c.get(b+'/rendering',headers=h).json()
    assert not c.get(b+'/ranking',headers=h).json()['is_current']
    assert c.post(b+'/ranking',headers=h,json=request).status_code==409
    req={'expected_render_revision':new['revision'],'expected_candidate_ids':[v['candidate_id'] for v in new['candidates']]}
    c.post(b+'/ranking',headers=h,json=req)
    latest=c.get(b+'/ranking',headers=h).json()
    assert latest['is_current'] and latest['revision']==2 and latest['ranking']!=first['ranking']


def test_dedup_and_change_while_inflight(service):
    app,c,h,m,b,request,r=rendered(service)
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']); store=app.state.ranking_store
    body=RankingRequest.model_validate(request)
    first,task=store.start(owner,m['job_id'],body)
    second,none=store.start(owner,m['job_id'],body)
    assert none is None and first==second
    changed=draft();changed['product_features']='바뀐 상품 특징'
    c.put(b+'/input',headers=h,json=changed)
    store.finish(owner,m['job_id'],task)
    old=c.get(b+'/ranking',headers=h).json()
    assert old['status']=='completed' and not old['is_current']


def test_failure_safe_retry_and_render_preserved(service):
    app,c,h,m,b,request,r=rendered(service)
    class Broken:
        def rank(self,*args): raise RuntimeError('secret /internal/path')
    app.state.ranking_store.ranker=Broken()
    c.post(b+'/ranking',headers=h,json=request)
    result=c.get(b+'/ranking',headers=h).json()
    assert result['status']=='failed' and result['ranking'] is None and 'secret' not in json.dumps(result)
    assert c.get(b+'/rendering',headers=h).json()==r
    app.state.ranking_store.ranker=MockRanker()
    c.post(b+'/ranking',headers=h,json=request)
    assert c.get(b+'/ranking',headers=h).json()['status']=='completed'


@pytest.mark.parametrize('mode',['missing','corrupt','changed'])
def test_asset_snapshot_validation(service,mode):
    app,c,h,m,b,request,r=rendered(service)
    c.post(b+'/ranking',headers=h,json=request)
    record=app.state.upload_store.records[m['job_id']]
    path=record.derived[r['candidates'][0]['png']['asset_id']]
    if mode=='missing': path.unlink()
    elif mode=='corrupt': path.write_bytes(b'bad png')
    else: path.write_bytes(png(size=(1080,1350),mode='RGB')+b'changed-content')
    if mode=='changed':
        assert not c.get(b+'/ranking',headers=h).json()['is_current']
        assert c.post(b+'/ranking',headers=h,json=request).status_code==409
    else:
        assert c.get(b+'/ranking',headers=h).status_code==(404 if mode=='missing' else 409)


def test_expiry_while_inflight_and_cleanup(service):
    app,c,h,m,b,request,r=rendered(service)
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session']); store=app.state.ranking_store
    _,task=store.start(owner,m['job_id'],RankingRequest.model_validate(request))
    app.state.upload_store.records[m['job_id']].upload.expires_at=now()-timedelta(seconds=1)
    store.finish(owner,m['job_id'],task)
    assert c.get(b+'/ranking',headers=h).status_code==410
    app.state.upload_store.cleanup()
    assert m['job_id'] not in app.state.upload_store.records


@pytest.mark.parametrize('mode',['few','many','duplicate','strategy','revision'])
def test_corrupted_render_never_ranked(service,mode):
    app,c,h,m,b,request,r=rendered(service)
    record=app.state.upload_store.records[m['job_id']]
    current=record.renders[record.last_render]
    if mode=='few': current.candidates.pop()
    elif mode=='many': current.candidates.append(current.candidates[0])
    elif mode=='duplicate': current.candidates[1].candidate_id=current.candidates[0].candidate_id
    elif mode=='strategy': current.candidates[1].strategy=current.candidates[0].strategy
    else: current.candidates[0].png.revision=9
    assert c.post(b+'/ranking',headers=h,json=request).status_code==409
