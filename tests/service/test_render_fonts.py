import json
import os
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from app.services import render_fonts as fonts
from app.services.render_execution import RenderFailure
from app.services.diagnostics_engine import fonts as diagnose


def test_bundled_faces_integrity_axes_and_offline_css():
    css, fingerprint = fonts.load_fonts('한글 English 6,500원 ₩')
    assert len(fingerprint) == 64 and 'https://' not in css
    assert "font-family:'Noto Serif KR'" in css and "font-family:'Pretendard'" in css
    manifest = json.loads((fonts.ASSETS/'manifest.json').read_text())
    for entry in manifest['faces'][2:]:
        with TTFont(fonts.ROOT/entry['path']) as font:
            axis = next(a for a in font['fvar'].axes if a.axisTag=='wght')
            low,high = map(float,entry['weight'].split())
            assert (low,high)==(axis.minValue,axis.maxValue)
            assert all(ord(c) in font.getBestCmap() for c in '한글 English 6,500원 ₩')


@pytest.mark.parametrize('corrupt',[False,True])
def test_missing_corrupt_face_fails_closed_and_identity_changes(monkeypatch,tmp_path,corrupt):
    original=fonts.font_identity()
    manifest=json.loads((fonts.ASSETS/'manifest.json').read_text())
    missing=tmp_path/'missing.ttf'
    if corrupt:missing.write_bytes(b'not a font')
    manifest['faces'][2]['path']=str(missing)
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(fonts,'ASSETS',tmp_path)
    assert fonts.font_identity()!=original
    with pytest.raises(RenderFailure) as e:fonts.load_fonts('한글')
    assert e.value.code=='RENDER_FONT_UNAVAILABLE'


def test_default_roles_unchanged_and_explicit_comparison_profile():
    texts=[{'field':'headline','font_size_px':35},{'field':'body','font_size_px':28},
           {'field':'store_name','font_size_px':28},{'field':'unknown','font_size_px':10}]
    current=diagnose(texts)
    assert all(i['status']=='caution' and i['threshold']==36 for i in current.measured_value['items'])
    compared=diagnose(texts,{'headline':36,'body':28,'brand':28})
    assert [i['status'] for i in compared.measured_value['items']]==['caution','normal','normal','caution']
    assert '운영 기준 아님' in compared.criterion
    with pytest.raises(ValueError):diagnose(texts,{'body':float('nan')})


def test_active_family_embedding_keeps_fallback():
    css,_=fonts.load_fonts('한글',{'HanjangNoto','Pretendard'})
    assert "font-family:'HanjangNoto'" in css and "font-family:'Pretendard'" in css
    assert "font-family:'Noto Serif KR'" not in css


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
@pytest.mark.parametrize('family,actual',[('Noto Serif KR','Noto Serif KR'),('Pretendard','Pretendard Variable')])
def test_actual_chromium_family_weights_and_fallback(monkeypatch,family,actual):
    from test_template_v3 import data,photo
    from app.services.template_v3 import render_templates
    from dataclasses import replace
    original=fonts.load_fonts
    def isolated(text='',families=None):
        css,identity=original(text,{'HanjangNoto',family})
        return css+f".ad .text{{font-family:'{family}',HanjangNoto!important}}",identity
    monkeypatch.setattr(fonts,'load_fonts',isolated)
    # U+1100 is supported by the established input font but absent from Pretendard.
    row=render_templates(replace(data(),body='ᄀ 한글 English 6,500원'),photo(),['emotional_a'])[0]
    used={f['familyName'] for t in row['measurement']['text'] for f in t['actual_fonts']}
    # Variable Noto exposes its base face name (ExtraLight) through CDP even
    # when CSS selects a heavier wght axis; do not require a static-face name.
    assert any(actual in name for name in used)
    assert all(f['isCustomFont'] for t in row['measurement']['text'] for f in t['actual_fonts'])
    assert {t['font_weight'] for t in row['measurement']['text']} >= {400,700}
    if family=='Pretendard':assert 'Noto Sans KR' in used
    assert not row['measurement']['invalid']
