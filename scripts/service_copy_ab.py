"""Isolated text-only v5/v6 experiment. Default command prepares; never calls API.

Live execution requires separate human approval and --approved-two-paid-calls.
No server, .env, prompt source, ML or design file is changed by this tool.
"""
import argparse
import ast
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
import math
import os
import platform
from importlib.metadata import version as package_version
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.schemas.copy import Variants,STRATEGIES
from app.schemas.upload import InputDraft
from app.schemas.analysis import ClipResult,Palette
from app.services.uploads import validate_image
from app.services import copy_prompt,copy_openai
from app.services.copy_budget import CopyBudget,MAX_COST
from app.services.copy_contract import CopyFailure
from app.services.copy_quality import review_ad_copy
from app.services.copy_validation import validate_copy

V5='c8cb74a93cbdf99c9791d96927a237ca038f0172'
V6='9650c7ce5b4d56f5078fdc986ab152e59410fc13'
MODEL='gpt-5.4-mini-2026-03-17'
LEDGER=ROOT/'artifacts/copy-usage/ledger.json'
METRICS=['상품 적합성','광고 문구 매력도','한국어 자연스러움','전략 간 차별성','제목·본문·CTA 연결성','사실 주장 안전성','실제 광고 사용 의향']


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def prompts():
    result=[]
    for arm,ref,version in [('A',V5,'copy-v5-sensory-allowed'),('B',V6,'copy-v6-menu-identity')]:
        source=subprocess.check_output(['git','show',ref+':backend/app/services/copy_prompt.py'],cwd=ROOT).decode('utf-8')
        constants={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source).body
                   if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('SYSTEM_PROMPT','PROMPT_VERSION')}
        if constants['PROMPT_VERSION']!=version:raise ValueError('Pinned prompt version mismatch')
        text=constants['SYSTEM_PROMPT']
        result.append({'arm':arm,'ref':ref,'version':version,'instructions':text,'sha256':sha256(text.encode()).hexdigest()})
    return result


def source_hashes():
    return {name:sha256((ROOT/name).read_bytes()).hexdigest() for name in [
        'backend/app/services/copy_openai.py','backend/app/services/copy_budget.py',
        'backend/app/services/copy_prompt.py','backend/app/services/copy_quality.py',
        'backend/app/services/copy_validation.py','backend/app/services/copy_particles.py',
        'backend/app/schemas/copy.py','scripts/service_copy_ab.py']}


def runtime_versions():
    return {'python':platform.python_version(),'openai':package_version('openai'),'pydantic':package_version('pydantic')}


def fixed_input():
    cases=json.loads(subprocess.check_output(['git','show',V6+':tests/fixtures/copy/menu_quality_phase1.json'],cwd=ROOT))
    return next(c['input'] for c in cases if c['case_id']=='jajang-no-features')


def ledger_snapshot(path):
    raw=path.read_bytes();data=json.loads(raw)
    calls=data.get('calls')
    if not isinstance(calls,list) or any(not isinstance(c,dict) or not isinstance(c.get('id'),str)
            or type(c.get('cost_ceiling_usd')) not in (int,float) or not math.isfinite(c['cost_ceiling_usd'])
            or c['cost_ceiling_usd']<0 for c in calls):raise ValueError('Invalid ledger')
    return {'sha256':sha256(raw).hexdigest(),'count':len(calls),'cost_ceiling_usd':sum(c['cost_ceiling_usd'] for c in calls)}


@contextmanager
def selected_prompt(text):
    # Process-local override only. The two arms use exactly the same adapter and
    # current validator. No file writes and no shared server interpreter.
    previous=(copy_prompt.SYSTEM_PROMPT,copy_openai.SYSTEM_PROMPT)
    copy_prompt.SYSTEM_PROMPT=copy_openai.SYSTEM_PROMPT=text
    try:yield
    finally:copy_prompt.SYSTEM_PROMPT,copy_openai.SYSTEM_PROMPT=previous


def photo_snapshot(photo):
    raw=photo.read_bytes()
    dims=validate_image(raw,'image/jpeg' if photo.suffix.lower() in ('.jpg','.jpeg') else 'image/png')
    return {'sha256':sha256(raw).hexdigest(),'size':list(dims[:2]),'mime':dims[2]}


def selected_cues(clip,policy):
    if policy not in ('full','top1-per-category','none'):raise ValueError('Unknown common analysis policy')
    if clip.status!='available' or policy=='none':return []
    if policy=='full':return clip.cues
    return [max([c for c in clip.cues if c.category==category],key=lambda c:(c.similarity,c.candidate_id))
            for category in ['category','appearance','impression'] if any(c.category==category for c in clip.cues)]


def prepare(output,ledger=LEDGER,*,photo=None,analysis=None,analysis_policy='full'):
    if output.exists():raise ValueError('Use a new experiment directory')
    draft=InputDraft.model_validate(fixed_input());image=photo_snapshot(photo) if photo else None
    snapshot_analysis=None;clip=ClipResult()
    if analysis:
        supplied=json.loads(analysis.read_text(encoding='utf-8'))
        if image is None or supplied['source_sha256']!=image['sha256'] or supplied['selected_photo']!='original' or not supplied['original_unchanged']:
            raise ValueError('Analysis/photo mismatch')
        clip=ClipResult.model_validate(supplied['clip']);palette=Palette.model_validate_json(json.dumps(supplied['palette']))
        snapshot_analysis={'source_sha256':supplied['source_sha256'],'clip':clip.model_dump(mode='json'),'palette':palette.model_dump(mode='json')}
    payload=copy_prompt.provider_payload(draft,{'visual_hints':selected_cues(clip,analysis_policy)})
    arms=prompts();snapshot=ledger_snapshot(ledger)
    if snapshot['count']!=8 or snapshot['cost_ceiling_usd']+2*MAX_COST>.1:
        raise ValueError('Expected preserved eight-call ledger with room for two reservations')
    original=json.loads(ledger.read_bytes())['calls']
    if any(c.get('state')!='completed' or c.get('usage_known') is not True for c in original):
        raise ValueError('Existing ledger contains unfinished or unknown usage')
    for arm in arms:
        with selected_prompt(arm['instructions']):
            arm['input_bound_bytes']=copy_prompt.input_bound(payload)
            if arm['input_bound_bytes']>6000:raise ValueError('Input bound exceeded')
    plan={'status':'awaiting_paid_approval','model':MODEL,'draft':draft.model_dump(mode='json'),
        'payload':payload,'payload_sha256':digest(payload),'schema_sha256':digest(Variants.model_json_schema()),
        'generation':{'reasoning':{'effort':'none'},'max_output_tokens':2048,'store':False,'sdk_retries':0,'app_retries':0},
        'arms':arms,'runtime':runtime_versions(),'ledger_before':snapshot,'max_requests':10,'budget_usd':.1,
        'experiment_max_calls':2,'experiment_cost_ceiling_usd':2*MAX_COST,'source_hashes':source_hashes(),
        'validation_policy':'same current validator for A and B; no retry or correction on rejection',
        'photo':image,'photo_analysis':snapshot_analysis,'analysis_policy':analysis_policy,
        'photo_status':'user_selected_original_same_for_both_arms' if image else 'not supplied; placeholder preview cannot assess product identity or commercial image quality'}
    output.mkdir(parents=True);write_json(output/'plan.json',plan)
    (output/'plan.sha256').write_text(digest(plan),encoding='ascii')
    # Pending cells, not artificial quality scores or fabricated model output.
    import csv
    with (output/'human-evaluation.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['strategy','criterion','A_score_1_to_5','B_score_1_to_5','evaluator','notes','status'])
        for strategy in STRATEGIES:
            for metric in METRICS:w.writerow([strategy,metric,'','','','','not_evaluated'])
    write_json(output/'evaluation-status.json',{'real_llm_calls':0,'human_evaluation':'not_started',
        'ai_subjective_assessment':'not_started','image_commercial_quality':'not_evaluated','top_3_quality_issues':'not_evaluated'})
    write_json(output/'image-review-template.json',{k:{'human_status':'not_evaluated','notes':None} for k in [
        'product_photo_presence','line_breaks','title_body_price_hierarchy','contrast_readability',
        'photo_background_harmony','cta_naturalness','commercial_quality']})
    return plan


def verify_plan(plan,ledger,photo=None):
    if plan['arms']!=[{**p,'input_bound_bytes':a['input_bound_bytes']} for p,a in zip(prompts(),plan['arms'])]:
        raise ValueError('Pinned prompt changed')
    if plan['model']!=MODEL or plan['source_hashes']!=source_hashes():raise ValueError('Code changed; prepare and approve again')
    if plan['runtime']!=runtime_versions():raise ValueError('Runtime changed; prepare and approve again')
    if digest(plan['payload'])!=plan['payload_sha256'] or digest(Variants.model_json_schema())!=plan['schema_sha256']:
        raise ValueError('Payload/schema changed')
    d=InputDraft.model_validate(plan['draft'])
    if d.model_dump()!=InputDraft.model_validate(fixed_input()).model_dump():raise ValueError('Fixed synthetic case changed')
    if plan.get('photo') is not None and (photo is None or photo_snapshot(photo)!=plan['photo']):raise ValueError('Photo changed/missing')
    analysis=plan.get('photo_analysis');clip=ClipResult.model_validate(analysis['clip']) if analysis else ClipResult()
    if analysis and (plan.get('photo') is None or analysis['source_sha256']!=plan['photo']['sha256']):raise ValueError('Analysis mismatch')
    if copy_prompt.provider_payload(d,{'visual_hints':selected_cues(clip,plan['analysis_policy'])})!=plan['payload']:raise ValueError('Input differs')
    if plan['generation']!={'reasoning':{'effort':'none'},'max_output_tokens':2048,'store':False,'sdk_retries':0,'app_retries':0}:
        raise ValueError('Generation settings changed')
    if plan['max_requests']!=10 or plan['budget_usd']!=.1 or plan['experiment_max_calls']!=2 or plan['experiment_cost_ceiling_usd']!=2*MAX_COST:
        raise ValueError('Limits changed')
    if ledger_snapshot(ledger)!=plan['ledger_before']:raise ValueError('Ledger changed; stop and review remaining allowance')
    for a in plan['arms']:
        with selected_prompt(a['instructions']):
            if copy_prompt.input_bound(plan['payload'])!=a['input_bound_bytes'] or a['input_bound_bytes']>6000:raise ValueError('Input bound changed')


def execute(output,ledger,*,approved=False,client=None,key=None,photo=None):
    if not approved:raise ValueError('Separate explicit approval required')
    plan=json.loads((output/'plan.json').read_text(encoding='utf-8'))
    if (output/'plan.sha256').read_text(encoding='ascii')!=digest(plan):raise ValueError('Plan changed')
    verify_plan(plan,ledger,photo)
    original=json.loads(ledger.read_bytes())['calls']
    mode='offline_fake_sdk' if client is not None else 'real_openai'
    if client is None:
        from app.config import Settings
        settings=Settings()
        if ledger.resolve()!=settings.copy_budget_path.resolve():raise ValueError('Must reuse configured existing ledger')
        if not settings.openai_api_key:raise ValueError('Server API key missing')
        key=settings.openai_api_key.get_secret_value()
    # Persistent single-use fence: never auto-resume after any attempted run.
    fd=os.open(output/'execution-started.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump({'status':'started','plan_sha256':digest(plan)},f)
    expected=plan['ledger_before'];results=[]
    provider=copy_openai.OpenAICopyProvider(MODEL,key or 'synthetic-offline-only',True,CopyBudget(ledger,10,.1),client=client)
    try:
        for arm in plan['arms']:
            if ledger_snapshot(ledger)!=expected:raise ValueError('Concurrent ledger change; no further dispatch')
            if plan.get('photo') is not None and photo_snapshot(photo)!=plan['photo']:raise ValueError('Photo changed; no further dispatch')
            folder=output/arm['arm'];folder.mkdir();usage=None;reply=None
            record={'arm':arm['arm'],'prompt_version':arm['version'],'status':'failed','usage':None,'error':None}
            try:
                with selected_prompt(arm['instructions']):reply=provider.generate(plan['payload'])
                usage=reply.usage
                (folder/'raw.txt').write_bytes(reply.text.encode('utf-8'))
                validated=validate_copy(reply.text,InputDraft.model_validate(plan['draft']))
                write_json(folder/'bound.json',validated.model_dump(mode='json',by_alias=True))
                product=plan['draft']['facts']['product_name'];price=plan['draft']['facts']['price_text']
                record.update(status='passed',warnings=review_ad_copy(validated.variants),
                    lengths=[{'strategy':v.strategy,**{k:len(t) for k,t in v.ad_copy.model_dump().items()}} for v in validated.variants],
                    automatic_checks={'exact_product_mentioned':{v.strategy:product in ' '.join(v.ad_copy.model_dump().values()) for v in validated.variants},
                        'price_strategy_verbatim_price':any(v.strategy=='price' and price in ' '.join(v.ad_copy.model_dump().values()) for v in validated.variants),
                        'schema_and_local_guards':'passed; not semantic fact certification',
                        'advertising_appeal':'not_automatically_scored'})
            except CopyFailure as e:
                usage=e.usage or usage;record['error']=e.code
            except Exception:
                record['error']='EXPERIMENT_FAILED'
            record['usage']=asdict(usage) if usage else None
            record['ledger_after']=ledger_snapshot(ledger);write_json(folder/'result.json',record);results.append(record)
            prefix_unchanged=json.loads(ledger.read_bytes())['calls'][:len(original)]==original
            write_json(output/'run.json',{'mode':mode,'results':results,'original_records_unchanged':prefix_unchanged,'ledger_before':plan['ledger_before'],
                'ledger_after':record['ledger_after'],'human_evaluation':'not_started','ai_subjective_assessment':'not_started'})
            write_json(output/'evaluation-status.json',{'mode':mode,
                'real_llm_calls':0 if mode=='offline_fake_sdk' else len(results) if all(r['status']=='passed' for r in results) else None,
                'potentially_billable_attempts':0 if mode=='offline_fake_sdk' else record['ledger_after']['count']-plan['ledger_before']['count'],
                'human_evaluation':'not_started','ai_subjective_assessment':'not_started',
                'image_commercial_quality':'not_evaluated','top_3_quality_issues':'not_evaluated'})
            expected=record['ledger_after']
            if not prefix_unchanged:raise ValueError('Original ledger records changed; no further dispatch')
            if record['status']!='passed':break  # no retry, repair or next arm after failure
            if expected['count']!=plan['ledger_before']['count']+len(results):break
    finally:provider.close()
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','execute'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--approved-two-paid-calls',action='store_true')
    p.add_argument('--photo',type=Path);p.add_argument('--analysis',type=Path)
    p.add_argument('--analysis-policy',choices=['full','top1-per-category','none'],default='full')
    args=p.parse_args()
    try:
        if args.command=='prepare':
            plan=prepare(args.output,photo=args.photo,analysis=args.analysis,analysis_policy=args.analysis_policy);print(json.dumps({'status':plan['status'],'max_calls':2,'reserved_cost_max':2*MAX_COST,'real_calls':0}));return 0
        if not args.approved_two_paid_calls:
            print('Not executed: separate explicit approval missing.');return 2
        results=execute(args.output,LEDGER,approved=True,photo=args.photo)
        print(json.dumps({'attempted_arms':len(results),'statuses':[r['status'] for r in results]}));return 0 if len(results)==2 and all(r['status']=='passed' for r in results) else 1
    except Exception:
        print('Stopped safely; inspect the local plan/results. No automatic retry.');return 1


if __name__=='__main__':raise SystemExit(main())
