"""A adapter/worker protocol tests use fake local processes; real weights are opt-in."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from app.ml_adapter.real_ranker import RealRanker, RankFailure
from app.schemas.ranking import Ranking, RankingRequest
from app.config import Settings
from test_rendering import service, png, draft
from test_ranking import rendered


def candidates():
    return [SimpleNamespace(candidate_id='c_'+s,revision=1) for s in ('emotional','price','visual','brand')]


@pytest.fixture
def fake_worker(tmp_path,monkeypatch):
    model=tmp_path/'bundle/model.safetensors';model.parent.mkdir();model.write_bytes(b'fake unit weights')
    ranker=RealRanker(Path(sys.executable),model,tmp_path/'snapshots',timeout=3)
    launched=[];real=subprocess.Popen
    def launch(args,**kwargs):
        if args[0]=='taskkill': return real(args,**kwargs)
        launched.append(args)
        script='''import sys,json,time,os
for line in sys.stdin:
 m=json.loads(line)
 items=[]
 for n,i in enumerate(m['items']):
  with open(i['rendered_image_path'],'rb') as f: assert f.read().startswith(b'\\x89PNG')
  items.append(dict(candidate_id=i['candidate_id'],score=1.,rank=1))
 for n,i in enumerate(sorted(items,key=lambda i:i['candidate_id'])):i['rank']=n+1
 mode=os.environ.get('UNIT_RANK_FAILURE')
 if mode=='unknown':items[0]['candidate_id']='unknown'
 if mode=='nan':items[0]['score']=float('nan')
 if mode=='rank':items[0]['rank']=9
 if mode=='order':items.reverse()
 print(json.dumps(dict(request_id=m['request_id'],result=dict(model_version='fake-unit-v1',feature_version='fake-features',items=items,pairwise=None),metrics=dict(model_loads=1))),flush=True)
'''
        return real([sys.executable,'-u','-c',script],**kwargs)
    monkeypatch.setattr('app.ml_adapter.real_ranker.subprocess.Popen',launch)
    yield ranker,launched
    ranker.close()


def test_default_model_mode_preserves_file_setting():
    s=Settings(_env_file=None)
    assert s.ranking_mode=='model' and s.ranking_model_path.name=='model.safetensors'


def test_worker_id_mapping_ties_cache_and_private_snapshot_cleanup(fake_worker):
    ranker,launched=fake_worker;cs=candidates();data={c.candidate_id:png() for c in cs}
    first=ranker.rank_snapshot(cs,1,data)
    second=ranker.rank_snapshot(list(reversed(cs)),1,data)
    assert first==second and len(launched)==1
    assert [i.candidate_id for i in first.items]==sorted(data)
    assert first.source=='model' and first.model_version=='fake-unit-v1'
    assert not list(ranker.temp_root.iterdir())
    assert ranker.last_metrics['model_loads']==1


def test_missing_environment_model_and_repair(fake_worker):
    ranker,_=fake_worker;cs=candidates();data={c.candidate_id:png() for c in cs}
    original=ranker.model_file;ranker.model_file=original.parent/'missing'
    with pytest.raises(RankFailure,match='RANKING_MODEL_UNAVAILABLE'):ranker.rank_snapshot(cs,1,data)
    ranker.model_file=original;python=ranker.python;ranker.python=Path('/missing-python')
    with pytest.raises(RankFailure,match='RANKING_ENV_UNAVAILABLE'):ranker.rank_snapshot(cs,1,data)
    ranker.python=python
    assert ranker.rank_snapshot(cs,1,data).source=='model'


@pytest.mark.parametrize('mode',['unknown','nan','rank','order'])
def test_invalid_worker_result_is_rejected_and_retry_recovers(fake_worker,monkeypatch,mode):
    ranker,launched=fake_worker;cs=candidates();data={c.candidate_id:png() for c in cs}
    monkeypatch.setenv('UNIT_RANK_FAILURE',mode)
    with pytest.raises(RankFailure,match='RANKING_OUTPUT_INVALID'):ranker.rank_snapshot(cs,1,data)
    assert ranker.process is None and not list(ranker.temp_root.iterdir())
    monkeypatch.delenv('UNIT_RANK_FAILURE')
    assert ranker.rank_snapshot(cs,1,data).source=='model' and len(launched)==2


def test_timeout_kills_owned_worker_and_cleans_snapshot(tmp_path,monkeypatch):
    model=tmp_path/'model';model.write_bytes(b'unit')
    ranker=RealRanker(Path(sys.executable),model,tmp_path/'snapshots',timeout=.05)
    real=subprocess.Popen
    monkeypatch.setattr('app.ml_adapter.real_ranker.subprocess.Popen',
        lambda args,**kwargs:real(args if args[0]=='taskkill' else [sys.executable,'-u','-c','import time;time.sleep(10)'],**kwargs))
    cs=candidates()
    with pytest.raises(RankFailure,match='RANKING_TIMEOUT'):ranker.rank_snapshot(cs,1,{c.candidate_id:png() for c in cs})
    assert ranker.process is None and not list(ranker.temp_root.iterdir())


@pytest.mark.parametrize('failure',['RANKING_ARTIFACT_INVALID','RANKING_INFERENCE_FAILED','RANKING_MODEL_UNAVAILABLE'])
def test_model_failure_no_fallback_and_other_features_survive(service,failure):
    app,c,h,m,b,request,r=rendered(service)
    class Failing:
        mode='model'
        def rank_snapshot(self,*args):raise RankFailure(failure)
    app.state.ranking_store.ranker=Failing()
    assert c.post(b+'/ranking',headers=h,json=request).status_code==202
    result=c.get(b+'/ranking',headers=h).json()
    assert result['status']=='failed' and result['ranking'] is None and result['error']['code']==failure
    assert 'RANKING_MODEL_MODE' in result['warnings']
    assert c.get(b+'/rendering',headers=h).json()==r
    assert c.get(r['candidates'][0]['png']['url'],headers=h).status_code==200
    assert c.get(b+'/editing',headers=h).status_code==200


def test_real_snapshot_inflight_revision_and_bundle_change(service):
    app,c,h,m,b,request,r=rendered(service)
    class SnapshotRanker:
        mode='model';version='one'
        def cache_token(self):return self.version
        def rank_snapshot(self,cs,revision,pngs):
            assert set(pngs)=={x.candidate_id for x in cs}
            assert all(raw.startswith(b'\x89PNG') for raw in pngs.values())
            return Ranking(source='model',model_version='unit-v1',feature_version='unit-features',revision=revision,
                items=[{'candidate_id':x.candidate_id,'score':1.,'rank':n+1} for n,x in enumerate(sorted(cs,key=lambda x:x.candidate_id))])
    ranker=SnapshotRanker();store=app.state.ranking_store;store.ranker=ranker
    owner=app.state.upload_store.authenticate(h['X-Hanjang-Session'])
    _,task=store.start(owner,m['job_id'],RankingRequest.model_validate(request))
    changed=draft();changed['product_features']='changed';c.put(b+'/input',headers=h,json=changed)
    store.finish(owner,m['job_id'],task)
    assert not c.get(b+'/ranking',headers=h).json()['is_current']
    c.put(b+'/input',headers=h,json=draft())
    c.post(b+'/ranking',headers=h,json=request)
    assert c.get(b+'/ranking',headers=h).json()['is_current']
    ranker.version='two'
    assert not c.get(b+'/ranking',headers=h).json()['is_current']


@pytest.mark.skipif(os.getenv('RUN_RANKING_TESTS')!='1',reason='explicit local B bundle/.venv-rank required; never download in CI')
def test_actual_b_bundle_inference_scores_mapping_cache(tmp_path):
    settings=Settings(_env_file=None)
    ranker=RealRanker(settings.ranking_python,settings.ranking_model_path,tmp_path/'actual',timeout=60)
    cs=candidates();data={c.candidate_id:Path('tests/fixtures/ads',c.candidate_id[2:]+'.png').read_bytes() for c in cs}
    expected=json.loads(Path('ml/inference/smoke_expected.json').read_text())
    try:
        result=ranker.rank_snapshot(cs,1,data)
        first=dict(ranker.last_metrics)
        reordered=ranker.rank_snapshot(list(reversed(cs)),1,data)
        assert result==reordered and ranker.last_metrics['model_loads']==1 and ranker.last_metrics['load_seconds']==0
        assert result.model_version==expected['model_version'] and result.source=='model'
        for item in result.items:
            assert item.rank==expected['items'][item.candidate_id]['rank']
            assert item.score==pytest.approx(expected['items'][item.candidate_id]['score'],abs=.001)
        print('REAL_MODEL_METRICS',first,ranker.last_metrics)
    finally:ranker.close()


@pytest.mark.skipif(os.getenv('RUN_RANKING_TESTS')!='1',reason='explicit local ranking environment; never install/download in CI')
@pytest.mark.parametrize('broken',['manifest_missing','corrupt_weight'])
def test_actual_b_loader_rejects_broken_private_bundle(tmp_path,broken):
    settings=Settings(_env_file=None);bundle=tmp_path/'broken';bundle.mkdir()
    model=bundle/'model.safetensors';model.write_bytes(b'not a model')
    if broken=='corrupt_weight':
        manifest=(settings.ranking_model_path.parent/'manifest.json').read_bytes()
        (bundle/'manifest.json').write_bytes(manifest)
    ranker=RealRanker(settings.ranking_python,model,tmp_path/'snapshots',timeout=60)
    cs=candidates()
    try:
        with pytest.raises(RankFailure) as caught:
            ranker.rank_snapshot(cs,1,{c.candidate_id:png(size=(1080,1350)) for c in cs})
        assert caught.value.code==('RANKING_MODEL_UNAVAILABLE' if broken=='manifest_missing' else 'RANKING_ARTIFACT_INVALID')
        assert ranker.process is None
    finally:ranker.close()
