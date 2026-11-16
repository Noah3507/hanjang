"""Export only scores, identifiers and verification flags from a private review.

No inference, network calls, photos, copy, local paths or model files are exported.
Run from repository root; all inputs must already exist locally.
"""
import argparse
import csv
from itertools import combinations
import json
import math
from pathlib import Path


def analyze(comparison, before, after, manifest):
    threshold=manifest['close_call_score_gap']
    if isinstance(threshold,bool) or not isinstance(threshold,(float,int)) or not math.isfinite(threshold) or threshold<=0:
        raise ValueError('Invalid manifest policy')
    metadata=[{r['template_id']:r for r in m['results']} for m in (before,after)]
    rows=[];pairs=[];summaries=[]
    for group in comparison:
        strategy=group['strategy'];versions=[group[k]['ranking'] for k in ('before','real-cutout')]
        for ranking in versions:
            if ranking['source']!='model' or ranking['model_version']!=manifest['model_version'] or ranking['feature_version']!=manifest['feature_version']:
                raise ValueError('Different model or feature version')
        old,new=[{i['candidate_id']:i for i in r['items']} for r in versions]
        if set(old)!=set(new) or len(old)!=4:raise ValueError('Incomplete comparison')
        for key in sorted(old):
            if not key.startswith('phase16-'):raise ValueError('Unknown input identity mapping')
            tid=key.removeprefix('phase16-')
            if tid not in {strategy+'_'+c for c in 'abcd'}:raise ValueError('Invalid template identity')
            b,a=[m[tid] for m in metadata]
            text=lambda row:{t['field']:t['text'] for t in row['measurement']['text'] if t['field'] in ('headline','body','cta')}
            rows.append(dict(strategy=strategy,template_id=tid,candidate_id=key,
                before_render_candidate_id=b.get('candidate_id'),after_render_candidate_id=a.get('candidate_id'),
                before_score=old[key]['score'],after_score=new[key]['score'],before_rank=old[key]['rank'],after_rank=new[key]['rank'],
                score_change=new[key]['score']-old[key]['score'],rank_gain=old[key]['rank']-new[key]['rank'],
                copy_identical=text(b)==text(a),png_identical=b['png_sha256']==a['png_sha256']))
        for label,items in [('before',old),('after',new)]:
            batch=[]
            for left,right in combinations(sorted(items),2):
                gap=abs(items[left]['score']-items[right]['score'])
                if not math.isfinite(gap):raise ValueError('Nonfinite score')
                batch.append(dict(strategy=strategy,version=label,template_a=left.removeprefix('phase16-'),template_b=right.removeprefix('phase16-'),
                    absolute_score_gap=gap,within_manifest_policy=gap<=threshold,below_analysis_0_2=gap<0.2))
            pairs.extend(batch)
            summaries.append(dict(strategy=strategy,version=label,pairs=len(batch),
                within_manifest_count=sum(p['within_manifest_policy'] for p in batch),within_manifest_ratio=sum(p['within_manifest_policy'] for p in batch)/len(batch),
                below_0_2_count=sum(p['below_analysis_0_2'] for p in batch),below_0_2_ratio=sum(p['below_analysis_0_2'] for p in batch)/len(batch)))
    return dict(model_version=manifest['model_version'],feature_version=manifest['feature_version'],close_call_score_gap=threshold,
        rank_gain_definition='before_rank - after_rank (positive means moved up)',
        verification=dict(source_photo_identical=before.get('source_sha256') is not None and before.get('source_sha256')==after.get('source_sha256'),
            copy_identical=all(r['copy_identical'] for r in rows),model_and_feature_versions_identical=True,
            final_pngs_identical=all(r['png_identical'] for r in rows),
            weight_identity='Same local RealRanker instance/bundle in Phase16 runner; no per-inference weight hash in source JSON, so historical equality not independently provable'),
        candidates=rows,pairs=pairs,summaries=summaries)


def main():
    p=argparse.ArgumentParser()
    for name in ['comparison','before-metadata','after-metadata','manifest']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args()
    report=analyze(*[json.loads(getattr(args,n).read_text(encoding='utf-8')) for n in ['comparison','before_metadata','after_metadata','manifest']])
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    (out/'scores.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['candidates','pairs','summaries']:
        with (out/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(report[name][0]));w.writeheader();w.writerows(report[name])
    lines=['# Phase 16 model score comparison','',
        f"Manifest policy: **{report['close_call_score_gap']}**, inclusive `gap <= policy`. Analysis-only comparator: strict `gap < 0.2`.",
        'Neither is validated statistical confidence or same-strategy ranking accuracy. Raw model scores are not CTR or conversion rates.',
        '', 'Source: the final Phase 16 `review-candidate-02/model-comparison.json`, with `before/metadata.json` and `real-cutout/metadata.json`.',
        'Local review directory is outside Git; only sanitized derived numbers/IDs are committed here. No images, copy or absolute paths are included.',
        '', '## Comparability','',json.dumps(report['verification'],ensure_ascii=False),
        '', 'Same source photo and copy; different final PNGs/layouts/fonts/placement. Changes are composite design changes, not a controlled estimate of one intervention.',
        'Model/feature version equality is checked. Same bundle use is supported by the Phase 16 runner; the JSON does not record weight hashes per call.',
        'Inference IDs `phase16-{template_id}` were assigned by the comparison runner. Render candidate IDs are separate and retained when available.',
        '', '## Candidate scores (display rounded only)','',
        '| Strategy | Template | Before score | After score | Before rank | After rank | Score change | Rank gain |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in report['candidates']:
        lines.append(f"| {r['strategy']} | {r['template_id']} | {r['before_score']:.6f} | {r['after_score']:.6f} | {r['before_rank']} | {r['after_rank']} | {r['score_change']:+.6f} | {r['rank_gain']:+d} |")
    lines+=['','## Six unordered pairs per strategy/version','','| Strategy | Version | Policy count/6 | Policy ratio | <0.2 count/6 | <0.2 ratio |','|---|---|---:|---:|---:|---:|']
    for s in report['summaries']:lines.append(f"| {s['strategy']} | {s['version']} | {s['within_manifest_count']}/6 | {s['within_manifest_ratio']:.2%} | {s['below_0_2_count']}/6 | {s['below_0_2_ratio']:.2%} |")
    for version in ['before','after']:
        subset=[v for v in report['pairs'] if v['version']==version];n=sum(v['below_analysis_0_2'] for v in subset)
        lines+=['',f'Aggregate {version}: strict <0.2 = {n}/{len(subset)} ({n/len(subset):.2%}).']
    lines+=['','## Reproduction','',
        'Run with existing Python; no model environment or inference needed. Paths below are placeholders, not private machine paths:',
        '```text','python scripts/service_ranking_comparison.py --comparison <review>/model-comparison.json --before-metadata <review>/before/metadata.json --after-metadata <review>/real-cutout/metadata.json --manifest <bundle>/manifest.json --output-dir <new-output>','```',
        'For reproduction without private review files, use `scores.json`: subtract each candidate score before rounding, enumerate `combinations(sorted(candidate_ids), 2)` (six pairs), and count `abs(left-right) <= close_call_score_gap` and separately `< 0.2`.',
        'JSON/CSV retain binary64 source score precision; Markdown formatting is display-only. Rank gain = before minus after. No missing facts or historical weight hashes are invented.']
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report['summaries']))


if __name__=='__main__':main()
