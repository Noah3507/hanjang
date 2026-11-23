"""Experiment safety tests use fake SDK and artificial ledgers only."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import service_copy_ab as ab
from app.services import copy_prompt,copy_openai
from test_openai_validation import no_network


@pytest.fixture
def prepared(tmp_path):
    ledger=tmp_path/'synthetic-ledger.json'
    calls=[{'id':f'synthetic-{i}','state':'completed','usage_known':True,'cost_ceiling_usd':.01274025 if i==0 else 0} for i in range(8)]
    ledger.write_text(json.dumps({'calls':calls}),encoding='utf-8')
    before=ledger.read_bytes();folder=tmp_path/'experiment'
    plan=ab.prepare(folder,ledger)
    assert ledger.read_bytes()==before
    return folder,ledger,plan,calls


class FakeClient:
    def __init__(self,outputs):self.outputs=iter(outputs);self.calls=[];self.responses=SimpleNamespace(create=self.create)
    def create(self,**kwargs):
        self.calls.append(deepcopy(kwargs));output=next(self.outputs)
        if isinstance(output,Exception):raise output
        return SimpleNamespace(output_text=output,status='completed',output=[],usage=SimpleNamespace(input_tokens=100,output_tokens=200))
    def close(self):pass


def text():
    cases=json.loads((ab.ROOT/'tests/fixtures/copy/menu_quality_phase1.json').read_text(encoding='utf-8'))
    return json.dumps(cases[0]['reference'],ensure_ascii=False)


def test_prepare_is_read_only_and_human_scores_pending(prepared):
    folder,ledger,plan,calls=prepared
    assert plan['status']=='awaiting_paid_approval' and plan['experiment_max_calls']==2
    assert plan['experiment_cost_ceiling_usd']==pytest.approx(.027432)
    assert plan['arms'][0]['version']=='copy-v5-sensory-allowed'
    assert plan['arms'][1]['version']=='copy-v6-menu-identity'
    assert all(a['input_bound_bytes']<=6000 for a in plan['arms'])
    assert len((folder/'human-evaluation.csv').read_text(encoding='utf-8-sig').splitlines())==29
    assert json.loads((folder/'evaluation-status.json').read_text())['real_llm_calls']==0


def test_no_approval_means_no_call_or_ledger_write(prepared):
    folder,ledger,plan,calls=prepared;client=FakeClient([text(),text()]);raw=ledger.read_bytes()
    with pytest.raises(ValueError,match='approval'):ab.execute(folder,ledger,client=client)
    assert client.calls==[] and ledger.read_bytes()==raw and not (folder/'execution-started.json').exists()


def test_only_instructions_differ_and_original_eight_records_preserved(prepared):
    folder,ledger,plan,original=prepared;client=FakeClient([text(),text()])
    before=(copy_prompt.SYSTEM_PROMPT,copy_openai.SYSTEM_PROMPT)
    results=ab.execute(folder,ledger,approved=True,client=client)
    assert [r['status'] for r in results]==['passed','passed'] and len(client.calls)==2
    assert client.calls[0]['instructions']==plan['arms'][0]['instructions']
    assert client.calls[1]['instructions']==plan['arms'][1]['instructions']
    a,b=[{k:v for k,v in kw.items() if k!='instructions'} for kw in client.calls]
    assert a==b and a['model']==ab.MODEL and a['max_output_tokens']==2048 and a['store'] is False
    records=json.loads(ledger.read_text())['calls'];assert len(records)==10 and records[:8]==original
    assert sum(c['cost_ceiling_usd'] for c in records)<.1
    assert (copy_prompt.SYSTEM_PROMPT,copy_openai.SYSTEM_PROMPT)==before
    assert (folder/'A/raw.txt').read_text(encoding='utf-8')==text()
    assert json.loads((folder/'run.json').read_text())['mode']=='offline_fake_sdk'
    assert json.loads((folder/'evaluation-status.json').read_text())['human_evaluation']=='not_started'
    with pytest.raises((ValueError,FileExistsError)):ab.execute(folder,ledger,approved=True,client=client)
    assert len(client.calls)==2


def test_raw_response_bytes_are_not_reformatted(prepared):
    folder,ledger,plan,original=prepared
    raw=json.dumps(json.loads(text()),ensure_ascii=False,indent=2)+'\n'
    ab.execute(folder,ledger,approved=True,client=FakeClient([raw,raw]))
    assert (folder/'A/raw.txt').read_bytes()==raw.encode('utf-8')


@pytest.mark.parametrize('bad',[json.dumps({'variants':[]}),ValueError('synthetic transport error')])
def test_failure_stops_before_b_and_never_retries(prepared,bad):
    folder,ledger,plan,original=prepared;client=FakeClient([bad,text()])
    results=ab.execute(folder,ledger,approved=True,client=client)
    assert len(client.calls)==len(results)==1 and results[0]['status']=='failed'
    assert not (folder/'B').exists()
    assert json.loads(ledger.read_text())['calls'][:8]==original
    assert len(json.loads(ledger.read_text())['calls'])==9
    if isinstance(bad,str):assert (folder/'A/raw.txt').read_text()==bad
    with pytest.raises((ValueError,FileExistsError)):ab.execute(folder,ledger,approved=True,client=client)
    assert len(client.calls)==1


@pytest.mark.parametrize('change',['ledger','prompt','input','limit','code'])
def test_changed_plan_or_ledger_aborts_without_dispatch(prepared,change,monkeypatch):
    folder,ledger,plan,original=prepared;client=FakeClient([text(),text()])
    if change=='ledger':ledger.write_text(json.dumps({'calls':original+[{'id':'other','cost_ceiling_usd':0}]}))
    elif change=='prompt':plan['arms'][0]['instructions']+='changed'
    elif change=='input':
        plan['draft']['facts']['product_name']='other';plan['payload']['product_name']='other';plan['payload_sha256']=ab.digest(plan['payload'])
    elif change=='limit':plan['experiment_max_calls']=3
    else:monkeypatch.setattr(ab,'source_hashes',lambda:{})
    ab.write_json(folder/'plan.json',plan)
    with pytest.raises(ValueError):ab.execute(folder,ledger,approved=True,client=client)
    assert client.calls==[] and not (folder/'execution-started.json').exists()


def test_same_photo_analysis_is_bound_without_transmitting_image(prepared,tmp_path):
    from PIL import Image
    folder,ledger,plan,original=prepared
    photo=tmp_path/'synthetic.jpg';Image.new('RGB',(300,300),'#ddd').save(photo)
    analysis=tmp_path/'analysis.json'
    ab.write_json(analysis,{'source_sha256':ab.photo_snapshot(photo)['sha256'],'selected_photo':'original','original_unchanged':True,
        'clip':{'status':'available','cues':[{'category':'category','candidate_id':'synthetic-food','label':'음식 추정','similarity':.25}]},
        'palette':{'status':'available','colors':[{'hex':'#DDDDDD','rgb':[221,221,221],'proportion':1.0}],'sampled_pixels':1}})
    folder=tmp_path/'photo-experiment';plan=ab.prepare(folder,ledger,photo=photo,analysis=analysis)
    client=FakeClient([text(),text()]);ab.execute(folder,ledger,approved=True,client=client,photo=photo)
    a,b=[json.loads(c['input'][0]['content']) for c in client.calls]
    assert a==b and len(a['visual_hints'])==1
    assert set(a)=={'store_name','product_name','price_text','mood','product_features','visual_hints'}
    assert 'image' not in str(client.calls[0]['input']).lower()


def test_photo_or_analysis_mismatch_stops_before_paid_dispatch(prepared,tmp_path):
    from PIL import Image
    folder,ledger,plan,original=prepared
    photo=tmp_path/'synthetic.jpg';Image.new('RGB',(300,300),'white').save(photo)
    folder=tmp_path/'photo-experiment';ab.prepare(folder,ledger,photo=photo)
    Image.new('RGB',(300,300),'black').save(photo)
    client=FakeClient([text(),text()])
    with pytest.raises(ValueError):ab.execute(folder,ledger,approved=True,client=client,photo=photo)
    assert client.calls==[]


def test_common_cue_policy_is_explicit_and_deterministic():
    from app.schemas.analysis import ClipResult
    clip=ClipResult.model_validate({'status':'available','cues':[
        {'category':category,'candidate_id':str(i),'label':'synthetic','similarity':i/10}
        for category in ['category','appearance','impression'] for i in range(4)]})
    assert len(ab.selected_cues(clip,'full'))==12
    assert [c.similarity for c in ab.selected_cues(clip,'top1-per-category')]==[.3,.3,.3]
    assert ab.selected_cues(clip,'none')==[]
    with pytest.raises(ValueError):ab.selected_cues(clip,'silent-auto-trim')
