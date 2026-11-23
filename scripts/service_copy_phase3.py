"""Single-use approved Phase 3 experiment; production prompt/server stay unchanged."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from hashlib import sha256
import service_copy_ab as ab
from copy_phase3_prompts import PROMPTS
from app.services.copy_budget import CopyBudget, MAX_COST
from app.services.copy_validation import validate_copy
from app.schemas.upload import InputDraft
from app.config import Settings

BASE=ab.ROOT/'artifacts/copy-quality-phase2/proposed-top3'
OUT=ab.ROOT/'artifacts/copy-quality-phase3'
PHOTO=ab.ROOT/'test-images/jjajang2.jpg'

def current_sources():
    return {**ab.source_hashes(),**{name:sha256((ab.ROOT/name).read_bytes()).hexdigest() for name in
        ['scripts/service_copy_phase3.py','scripts/copy_phase3_prompts.py']}}

def prepare():
    old=json.loads((BASE/'plan.json').read_text(encoding='utf-8'))
    run=json.loads((BASE/'run.json').read_text(encoding='utf-8'))
    assert old['runtime']==ab.runtime_versions() and old['model']==ab.MODEL
    assert run['mode']=='real_openai' and run['original_records_unchanged']
    assert [r['status'] for r in run['results']]==['passed','passed']
    assert ab.ledger_snapshot(ab.LEDGER)==run['ledger_after']
    assert run['ledger_after']['count']==10 and abs(run['ledger_after']['cost_ceiling_usd']-.01628625)<1e-12
    assert ab.photo_snapshot(PHOTO)==old['photo'] and old['analysis_policy']=='top1-per-category'
    # Only the separately authorized budget opt-in may differ from Phase 2.
    for name,h in old['source_hashes'].items():
        if name!='backend/app/services/copy_budget.py':assert sha256((ab.ROOT/name).read_bytes()).hexdigest()==h
    assert 2*MAX_COST<=.027432 and run['ledger_after']['cost_ceiling_usd']+2*MAX_COST<=.1
    rendered=json.loads((BASE/'rendered-v3/render-review.json').read_text(encoding='utf-8'))
    for name,h in rendered['renderer_source_hashes'].items():assert sha256((ab.ROOT/name).read_bytes()).hexdigest()==h
    baseline=json.loads((BASE/'B/bound.json').read_text(encoding='utf-8'))
    assert validate_copy((BASE/'B/raw.txt').read_text(encoding='utf-8'),InputDraft.model_validate(old['draft'])).model_dump(mode='json',by_alias=True)==baseline
    arms=[]
    for arm,prompt in PROMPTS.items():
        with ab.selected_prompt(prompt):bound=ab.copy_prompt.input_bound(old['payload'])
        assert bound<=6000
        arms.append({'arm':arm,'instructions':prompt,'input_bound_bytes':bound})
    plan={**{k:old[k] for k in ['model','draft','payload','schema_sha256','runtime','generation','photo','photo_analysis','analysis_policy']},
        'arms':arms,'ledger_before':ab.ledger_snapshot(ab.LEDGER),'max_requests':12,'budget_usd':.1,
        'max_new_calls':2,'reservation_ceiling':2*MAX_COST,'source_hashes':current_sources(),
        'baseline_raw_sha256':sha256((BASE/'B/raw.txt').read_bytes()).hexdigest(),
        'render_sources':rendered['renderer_source_hashes']}
    OUT.mkdir(exist_ok=False)
    ab.write_json(OUT/'plan.json',plan);(OUT/'plan.sha256').write_text(ab.digest(plan))
    print(json.dumps({'prepared':True,'bounds':[a['input_bound_bytes'] for a in arms],'max_new_calls':2,'reservation':2*MAX_COST}))

def execute():
    p=json.loads((OUT/'plan.json').read_text(encoding='utf-8'))
    assert ab.digest(p)==(OUT/'plan.sha256').read_text() and p['source_hashes']==current_sources()
    assert ab.ledger_snapshot(ab.LEDGER)==p['ledger_before'] and ab.photo_snapshot(PHOTO)==p['photo']
    assert p['runtime']==ab.runtime_versions() and p['reservation_ceiling']==2*MAX_COST<=.027432
    settings=Settings();assert settings.copy_budget_path.resolve()==ab.LEDGER.resolve() and settings.openai_api_key
    for name,h in p['render_sources'].items():assert sha256((ab.ROOT/name).read_bytes()).hexdigest()==h
    original=json.loads(ab.LEDGER.read_bytes())['calls']
    # Do not remove this fence or resume/retry a failed experiment.
    fd=os.open(OUT/'execution-started.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    import openai
    class Capture:
        def __init__(self):
            self.inner=openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(),base_url='https://api.openai.com/v1',timeout=30.,max_retries=0)
            self.responses=self;self.arm=None;self.count=0
        def create(self,**kwargs):
            assert self.count<2;self.count+=1
            ab.write_json(OUT/self.arm/'request.json',kwargs)
            response=self.inner.responses.create(**kwargs)
            ab.write_json(OUT/self.arm/'response.json',response.model_dump(mode='json'))
            return response
        def close(self):self.inner.close()
    client=Capture();provider=ab.copy_openai.OpenAICopyProvider(ab.MODEL,'managed-server-key',True,CopyBudget(ab.LEDGER,12,.1,approved_phase3=True),client=client)
    expected=p['ledger_before'];results=[]
    try:
        for arm in p['arms']:
            assert ab.ledger_snapshot(ab.LEDGER)==expected and ab.photo_snapshot(PHOTO)==p['photo']
            folder=OUT/arm['arm'];folder.mkdir();client.arm=arm['arm'];reply=None
            result={'arm':arm['arm'],'status':'failed','usage':None}
            try:
                with ab.selected_prompt(arm['instructions']):reply=provider.generate(p['payload'])
                (folder/'raw.txt').write_bytes(reply.text.encode('utf-8'))
                bound=validate_copy(reply.text,InputDraft.model_validate(p['draft']))
                ab.write_json(folder/'bound.json',bound.model_dump(mode='json',by_alias=True));result['status']='passed'
            except ab.CopyFailure as error:
                result['error']=error.code;result['usage']=asdict(error.usage) if error.usage else None
            except Exception:result['error']='EXPERIMENT_FAILED'
            if reply:result['usage']=asdict(reply.usage)
            result['ledger_after']=ab.ledger_snapshot(ab.LEDGER);expected=result['ledger_after'];results.append(result)
            unchanged=json.loads(ab.LEDGER.read_bytes())['calls'][:10]==original
            ab.write_json(OUT/'run.json',{'mode':'real_openai','results':results,'original_ten_unchanged':unchanged,'ledger_after':expected})
            assert unchanged
            if result['status']!='passed':break
    finally:provider.close()
    print(json.dumps({'attempts':client.count,'statuses':[r['status'] for r in results]}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','execute']);parser.add_argument('--approved-two-paid-calls',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':prepare()
    elif args.approved_two_paid_calls:execute()
    else:raise SystemExit('No execution without explicit paid approval flag')
