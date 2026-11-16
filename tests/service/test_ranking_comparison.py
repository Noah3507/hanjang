"""Reproduce shared pair arithmetic without private input or model weights."""
import json
from itertools import combinations
from pathlib import Path


def test_shared_original_precision_scores_and_all_pairs():
    report=json.loads(Path('docs/analysis/phase16-ranking-review/scores.json').read_text(encoding='utf-8'))
    assert len(report['candidates'])==16 and len(report['pairs'])==48
    for s in report['summaries']:
        rows=[r for r in report['candidates'] if r['strategy']==s['strategy']]
        score={r['template_id']:r[s['version']+'_score'] for r in rows}
        pairs=[p for p in report['pairs'] if p['strategy']==s['strategy'] and p['version']==s['version']]
        assert {(p['template_a'],p['template_b']) for p in pairs}==set(combinations(sorted(score),2))
        for p in pairs:
            gap=abs(score[p['template_a']]-score[p['template_b']])
            assert p['absolute_score_gap']==gap
            assert p['within_manifest_policy']==(gap<=report['close_call_score_gap'])
            assert p['below_analysis_0_2']==(gap<0.2)
        assert s['below_0_2_count']==sum(p['below_analysis_0_2'] for p in pairs)
    assert report['verification']['source_photo_identical'] and report['verification']['copy_identical']
