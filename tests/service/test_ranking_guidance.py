import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.services.ranking_guidance import close_call_gap


@pytest.mark.parametrize('gap',[0.2,0.03125,None,True,0,-1,'0.2',float('nan')])
def test_bundle_policy_never_uses_fallback(tmp_path,gap):
    (tmp_path/'manifest.json').write_text(json.dumps({'model_version':'test','close_call_score_gap':gap}))
    ranker=SimpleNamespace(model_file=tmp_path/'model.safetensors')
    ranking=SimpleNamespace(source='model',model_version='test')
    assert close_call_gap(ranker,ranking)==(gap if type(gap) in (int,float) and gap>0 and gap==gap else None)
    assert close_call_gap(ranker,SimpleNamespace(source='mock')) is None
    ranking.model_version='other';assert close_call_gap(ranker,ranking) is None


def test_missing_or_invalid_manifest_does_not_block_ranking(tmp_path):
    r=SimpleNamespace(model_file=tmp_path/'model.safetensors');output=SimpleNamespace(source='model',model_version='test')
    assert close_call_gap(r,output) is None
    (tmp_path/'manifest.json').write_text('{broken')
    assert close_call_gap(r,output) is None
