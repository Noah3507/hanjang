"""Approved four-call v8 experiment. Default prepares only; one-use execution.

No prompt/default/server/ML changes. Uses the real existing ledger, never another.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.schemas.analysis import Cue
from app.schemas.upload import InputDraft
from app.services.copy_budget import CopyBudget,MAX_COST
from app.services.copy_prompt import provider_payload,input_bound
from app.services.copy_prompt_v8 import INSTRUCTIONS,VERSION
from app.services.copy_openai import OpenAICopyProvider
from app.services.copy_quality import review_ad_copy
from app.services.copy_validation import validate_copy
from app.services.copy_contract import CopyFailure

OUT=ROOT/'artifacts/copy-quality-phase4-live'
LEDGER=ROOT/'artifacts/copy-usage/ledger.json'
EXPECTED_LEDGER='85cc6a3ab965474ac9328383c46e591c442e4d1fc79fc76523e60d9f96986c6c'
MODEL='gpt-5.4-mini-2026-03-17'
ORDER=[('jjajang','menu_promotion'),('jjajang','store_visit'),('jjajang','order'),('espresso','menu_promotion')]
SOURCE_NAMES=['backend/app/services/copy_prompt_v8.py','backend/app/services/copy_prompt.py',
    'backend/app/services/copy_openai.py','backend/app/services/copy_budget.py','backend/app/services/copy_validation.py',
    'scripts/service_copy_phase4_live.py']

def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def digest(p):return sha256(p.read_bytes()).hexdigest()
def ledger_snapshot():
    data=json.loads(LEDGER.read_text(encoding='utf-8'))
    return {'sha256':digest(LEDGER),'count':len(data['calls']),
            'cost':str(sum((Decimal(str(c['cost_ceiling_usd'])) for c in data['calls']),Decimal(0)))}

def prepare():
    before=ledger_snapshot()
    assert before['sha256']==EXPECTED_LEDGER and before['count']==15 and Decimal(before['cost'])==Decimal('.02431050')
    assert abs(4*MAX_COST-.054864)<1e-12 and Decimal(before['cost'])+Decimal(str(4*MAX_COST))<=Decimal('.07917450')
    common=json.loads((ROOT/'artifacts/ad-quality-20261125/common-input.json').read_text(encoding='utf-8'))['cases']
    rows=[]
    for product,goal in ORDER:
        case=next(c for c in common if c['id']==product);photo=ROOT/case['photo']
        assert digest(photo)==case['photo_sha256']
        draft=InputDraft.model_validate({**case['draft'],'ad_goal':goal,'photo_mode':'cutout'})
        payload=provider_payload(draft,{'visual_hints':[Cue.model_validate(c) for c in case['analysis']['clip']['cues']]},'v8')
        bound=input_bound(payload,INSTRUCTIONS);assert bound<=6000 and len(payload['visual_hints'])==3
        rows.append({'id':product+'-'+goal,'product':product,'goal':goal,'draft':draft.model_dump(mode='json'),
            'payload':payload,'input_bound':bound,'photo':case['photo'],'photo_sha256':case['photo_sha256'],'analysis':case['analysis']})
    stripped=[{k:v for k,v in r['payload'].items() if k!='ad_goal'} for r in rows[:3]]
    assert stripped[0]==stripped[1]==stripped[2]
    OUT.mkdir(exist_ok=False)
    write(OUT/'plan.json',{'status':'사용자 승인 최대4회; 자동재시도0; 실패하면 남은 조건 중단',
        'main':subprocess.check_output(['git','rev-parse','origin/main'],cwd=ROOT,text=True).strip(),
        'model':MODEL,'prompt_version':VERSION,'instructions':INSTRUCTIONS,'ledger_before':before,
        'price_verified_source':'https://developers.openai.com/api/docs/models/gpt-5.4-mini',
        'price_verified_date':'2026-11-27','input_usd_per_million':.75,'output_usd_per_million':4.5,
        'max_reservation':4*MAX_COST,'source_hashes':{n:digest(ROOT/n) for n in SOURCE_NAMES},'cases':rows})
    print('Prepared: 4 conditions, existing ledger15, max additional $0.054864; no API call')

def execute():
    plan=json.loads((OUT/'plan.json').read_text(encoding='utf-8'))
    assert plan['model']==MODEL and plan['instructions']==INSTRUCTIONS and plan['prompt_version']==VERSION
    assert ledger_snapshot()==plan['ledger_before']
    assert all(digest(ROOT/n)==h for n,h in plan['source_hashes'].items())
    assert all(digest(ROOT/c['photo'])==c['photo_sha256'] for c in plan['cases'])
    settings=Settings() # Secret read only; never serialize settings or key.
    assert settings.openai_api_key and settings.copy_model==MODEL
    original=json.loads(LEDGER.read_text(encoding='utf-8'))['calls']
    # Exclusive marker prevents accidental second execution even after a failure.
    with (OUT/'execution-started').open('x',encoding='utf-8') as f:f.write('Approved run started; do not rerun.')
    import openai
    class Capture:
        def __init__(self):
            self.inner=openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(),base_url='https://api.openai.com/v1',timeout=30.,max_retries=0)
            self.responses=self;self.count=0;self.folder=None
        def create(self,**kwargs):
            assert self.count<4;self.count+=1
            write(self.folder/'request.json',kwargs)
            response=self.inner.responses.create(**kwargs)
            write(self.folder/'response.json',response.model_dump(mode='json'))
            return response
        def close(self):self.inner.close()
    capture=Capture();provider=OpenAICopyProvider(MODEL,'managed-server-key',True,
        CopyBudget(LEDGER,19,.1,approved_phase4=True),capture,prompt_profile='v8')
    expected=plan['ledger_before'];results=[]
    try:
        for case in plan['cases']:
            assert ledger_snapshot()==expected
            folder=OUT/case['id'];folder.mkdir(exist_ok=False);capture.folder=folder
            row={'id':case['id'],'status':'failed','usage':None};reply=None;t=time.perf_counter()
            try:
                reply=provider.generate(case['payload'])
                (folder/'raw.txt').write_text(reply.text,encoding='utf-8')
                response=json.loads((folder/'response.json').read_text(encoding='utf-8'))
                assert response['model']==MODEL
                bound=validate_copy(reply.text,InputDraft.model_validate(case['draft']))
                write(folder/'bound.json',bound.model_dump(mode='json',by_alias=True))
                row['warnings']=review_ad_copy(bound.variants,case['goal'],profile='v8',draft=InputDraft.model_validate(case['draft']))
                row['status']='passed'
            except CopyFailure as error:
                row['error']=error.code;row['usage']=asdict(error.usage) if error.usage else None
            except Exception:row['error']='EXPERIMENT_VERIFICATION_FAILED'
            if reply:row['usage']=asdict(reply.usage)
            row['seconds']=time.perf_counter()-t
            row['ledger_after']=ledger_snapshot();expected=row['ledger_after'];results.append(row)
            unchanged=json.loads(LEDGER.read_text(encoding='utf-8'))['calls'][:15]==original
            write(OUT/'run.json',{'mode':'실제 OpenAI v8','model':MODEL,'results':results,'attempts':capture.count,
                'original_fifteen_unchanged':unchanged,'ledger_after':expected,'automatic_retries':0})
            assert unchanged
            print(case['id'],row['status'],flush=True)
            if row['status']!='passed':break # no call after any failure
    finally:provider.close()
    print('Finished; paid attempts:',capture.count)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','execute'])
    parser.add_argument('--approved-four-paid-calls',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':prepare()
    elif args.approved_four_paid_calls:execute()
    else:raise SystemExit('Explicit approval flag required')
