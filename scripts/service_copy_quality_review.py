"""Offline copy review: Mock is real Mock output; reference is hand-authored.

No SDK, HTTP, images or real cost ledger is accessed. Not a production provider.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.schemas.upload import InputDraft
from app.services.copy_provider import MockCopyProvider
from app.services.copy_prompt import provider_payload,input_bound,PROMPT_VERSION
from app.services.copy_validation import validate_copy
from app.services.copy_quality import review_ad_copy


def evaluate(baseline_ref):
    old={}
    exec(compile(subprocess.check_output(['git','show',baseline_ref+':backend/app/services/copy_validation.py'],cwd=ROOT).decode('utf-8'),'<baseline-validator>','exec'),old)
    cases=json.loads((ROOT/'tests/fixtures/copy/menu_quality_phase1.json').read_text(encoding='utf-8'))
    results=[]
    for case in cases:
        draft=InputDraft.model_validate(case['input']);payload=provider_payload(draft,{'visual_hints':[]})
        mock_raw=MockCopyProvider().generate(payload).text
        reference_raw=json.dumps(case['reference'],ensure_ascii=False)
        old_reference=old['validate_copy'](reference_raw,draft)
        row={'case_id':case['case_id'],'input':draft.model_dump(mode='json'),'input_bound_bytes':input_bound(payload),
             'mock_provenance':'unchanged MockCopyProvider, not LLM','reference_provenance':case['provenance'],
             'mock_before':old['validate_copy'](mock_raw,draft).model_dump(mode='json',by_alias=True),
             'mock_after':validate_copy(mock_raw,draft).model_dump(mode='json',by_alias=True),
             'reference':validate_copy(reference_raw,draft).model_dump(mode='json',by_alias=True),
             'reference_old_validator':'passed'}
        assert row['mock_before']==row['mock_after']
        assert old_reference.model_dump(mode='json',by_alias=True)==row['reference']
        row['mock_warnings']=review_ad_copy(validate_copy(mock_raw,draft).variants)
        row['reference_warnings']=review_ad_copy(validate_copy(reference_raw,draft).variants)
        results.append(row)
    probes=[]
    draft=InputDraft.model_validate(cases[4]['input'])
    for text in ['매일 마시고 싶은 [[product_name]]','매일 먹고 싶은 한 조각','매일 갓 볶는 원두','매일 마시고 싶은 수제 커피']:
        raw=json.loads(MockCopyProvider().generate({}).text);raw['variants'][0]['copy']['body']=text;raw=json.dumps(raw,ensure_ascii=False)
        outcomes={}
        for name,check in [('before',old['validate_copy']),('after',validate_copy)]:
            try:check(raw,draft);outcomes[name]='passed'
            except Exception as e:outcomes[name]=getattr(e,'code',type(e).__name__)
        probes.append({'authored_probe':text,**outcomes})
    repeated=Counter(v['copy']['headline'] for r in results for v in r['mock_before']['variants'])
    return {'baseline_ref':baseline_ref,'prompt_version':PROMPT_VERSION,'paid_calls':0,
        'llm_before_after_comparison':'NOT RUN — requires separate paid approval',
        'cases':results,'mock_headline_counts':dict(repeated),'validator_probes':probes}


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline-ref',default='c8cb74a');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    report=evaluate(args.baseline_ref);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 음식점 카페 카피 오프라인 비교','',
        '**실제 LLM 전후 결과가 아닙니다.** 기존·개선 Mock 출력은 동일하며 목표 문구는 사람이 작성한 평가용 예시입니다. 유료 호출 0회.',
        '프롬프트 전달·검증·길이·사실 원문·조사를 검사했으며 광고 매력도 향상이나 실사용 생성 품질은 입증하지 않습니다.','']
    for r in report['cases']:
        lines+=[f"## {r['case_id']}",'', '`'+json.dumps(r['input'],ensure_ascii=False)+'`','',
            '| 전략 | 기존 고정 Mock 실제 출력 (제목 / 본문 / CTA) | 수작업 목표 예시 (LLM 아님) |', '|---|---|---|']
        for old,new in zip(r['mock_before']['variants'],r['reference']['variants']):
            parts=lambda v:' / '.join(v['copy'][k] for k in ('headline','body','cta'))
            lines.append(f"| {old['strategy']} | {parts(old)} | {parts(new)} |")
        lines+=['',f"검증: Mock/목표 예시 모두 통과. 입력 상한 계산 {r['input_bound_bytes']} bytes. Mock 경고 {r['mock_warnings']}; 목표 경고 {r['reference_warnings']}.",'']
    lines+=['## 검증 오탐과 위험 구분','', '| 수작업 검사 문구 | 기존 검증 | 개선 검증 |','|---|---|---|']
    lines += [f"| {v['authored_probe']} | {v['before']} | {v['after']} |" for v in report['validator_probes']]
    lines+=['','각 목표 문구는 특징 입력 유무에 따라 이유/선택 정보를 달리하도록 작성했습니다. 수작업 설계가 가능한 품질의 예시이지, 새 프롬프트가 이를 생성한다는 증거는 아닙니다.',
        '사진은 사용하지 않았고 visual_hints는 빈 배열입니다. 이미지 기반 단서 및 실제 모델의 변동성은 이 비교 범위 밖입니다.']
    (args.output/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(report['cases']),'reference_copies':len(report['cases'])*4,'paid_calls':0,'max_input_bound':max(r['input_bound_bytes'] for r in report['cases'])}))


if __name__=='__main__':main()
