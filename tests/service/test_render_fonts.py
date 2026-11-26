import json
import os
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont
from app.services import render_fonts as fonts
from app.services.render_execution import RenderFailure
from app.services.diagnostics_engine import fonts as diagnose
from test_designs import designs,generate,snap
from test_rendering import service


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
        return css+f".ad .text{{font-family:'{family}',HanjangNoto!important}}.ad .body{{font-weight:620!important}}",identity
    monkeypatch.setattr(fonts,'load_fonts',isolated)
    # U+1100 is supported by the established input font but absent from Pretendard.
    row=render_templates(replace(data(),body='ᄀ 한글 English 6,500원'),photo(),['emotional_a'])[0]
    used={f['familyName'] for t in row['measurement']['text'] for f in t['actual_fonts']}
    manifest=json.loads((fonts.ASSETS/'manifest.json').read_text())
    entry=next(f for f in manifest['faces'] if f['family']==family)
    assert any(fonts._subset_name(entry['sha256']) in name for name in used)
    assert all(f['isCustomFont'] for t in row['measurement']['text'] for f in t['actual_fonts'])
    assert {t['font_weight'] for t in row['measurement']['text']} >= {400,620,700}
    if family=='Pretendard':
        fallback=manifest['faces'][1]  # 620 selects the existing 700 fallback face.
        assert any(fonts._subset_name(fallback['sha256']) in name for name in used)
    assert not row['measurement']['invalid']


def test_faces_are_subset_to_the_ad_text():
    """Pages carry only the glyphs they show: the 24 MB serif becomes a few tens of KB."""
    import base64, re
    from io import BytesIO
    text = '골목반점 짜장면 7,000원 점심에 생각나는 짜장면'
    css, _ = fonts.load_fonts(text, {'HanjangNoto', 'Noto Serif KR', 'Pretendard'})
    faces = re.findall(r"font-family:'([^']+)';src:url\(data:[^;]+;base64,([A-Za-z0-9+/=]+)\)", css)
    assert {f for f, _ in faces} == {'HanjangNoto', 'Noto Serif KR', 'Pretendard'}
    for family, data in faces:
        raw = base64.b64decode(data)
        assert len(raw) < 500_000, family
        with TTFont(BytesIO(raw)) as font:
            assert all(ord(c) in font.getBestCmap() for c in text if not c.isspace()), family
            if family != 'HanjangNoto':
                assert 'wght' in [a.axisTag for a in font['fvar'].axes], family  # bold still works
    assert fonts.load_fonts(text, {'Pretendard'}) == fonts.load_fonts(text, {'Pretendard'})  # deterministic


def decoded(css):
    import base64,re
    from io import BytesIO
    return [TTFont(BytesIO(base64.b64decode(b))) for b in re.findall(r'base64,([A-Za-z0-9+/=]+)',css)]


def test_new_characters_canonical_cache_and_license_names():
    from collections import OrderedDict
    a=fonts.load_fonts('가ABC',{'Pretendard'})
    assert a==fonts.load_fonts('CBA가가',{'Pretendard'})
    first=decoded(a[0])[0];new=decoded(fonts.load_fonts('가ABC힣',{'Pretendard'})[0])[0]
    assert ord('힣') not in first.getBestCmap() and ord('힣') in new.getBestCmap()
    for f in (first,new):
        assert f['name'].getDebugName(1).startswith('HanjangSubset')
        assert 'Pretendard' not in f['name'].getDebugName(6)
        assert 'Copyright' in f['name'].getDebugName(0)
        assert {'GSUB','GPOS','fvar','gvar'} <= set(f.keys())
        axis=f['fvar'].axes[0];assert (axis.minValue,axis.maxValue)==(45,930)
        assert len(f['fvar'].instances)>0
        f.close()


def test_warm_cache_never_bypasses_source_integrity(monkeypatch,tmp_path):
    manifest=json.loads((fonts.ASSETS/'manifest.json').read_text())
    entry=manifest['faces'][3];file=tmp_path/'font.ttf';file.write_bytes((fonts.ROOT/entry['path']).read_bytes())
    entry['path']=str(file);(tmp_path/'manifest.json').write_text(json.dumps({'faces':[entry]}))
    monkeypatch.setattr(fonts,'ASSETS',tmp_path)
    fonts.load_fonts('한글',{'Pretendard'})
    file.write_bytes(b'corrupt after warmup')
    with pytest.raises(RenderFailure) as e:fonts.load_fonts('한글',{'Pretendard'})
    assert e.value.code=='RENDER_FONT_UNAVAILABLE'


def test_cache_entry_and_payload_limits(monkeypatch):
    from collections import OrderedDict
    monkeypatch.setattr(fonts,'_cache',OrderedDict());monkeypatch.setattr(fonts,'_cache_bytes',0)
    monkeypatch.setattr(fonts,'CACHE_MAX_ENTRIES',2)
    for text in ('가','나','다'):fonts.load_fonts(text,{'Pretendard'})
    assert len(fonts._cache)==2 and fonts._cache_bytes==sum(map(len,fonts._cache.values()))
    fonts._cache.clear();fonts._cache_bytes=0
    monkeypatch.setattr(fonts,'CACHE_MAX_ENTRIES',128)
    monkeypatch.setattr(fonts,'CACHE_MAX_BYTES',128000)
    for text in ('가','나','다','라'):fonts.load_fonts(text,{'Pretendard'})
    assert 0<len(fonts._cache)<4 and fonts._cache_bytes<=128000
    fonts._cache.clear();fonts._cache_bytes=0
    monkeypatch.setattr(fonts,'CACHE_MAX_BYTES',1)
    fonts.load_fonts('라',{'Pretendard'})
    assert not fonts._cache and fonts._cache_bytes==0


def test_subset_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(fonts,'_subset',lambda *a:(_ for _ in ()).throw(ValueError('private details')))
    with pytest.raises(RenderFailure) as e:fonts.load_fonts('한글')
    assert e.value.code=='RENDER_FONT_UNAVAILABLE'


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_actual_edit_new_characters_preserves_identity_contract(designs,monkeypatch):
    from app.services.template_v3 import render_templates
    app,c,h,m,b,body,v2=designs
    original=fonts.load_fonts
    def isolated(text='',families=None):
        css,key=original(text,{'HanjangNoto','Pretendard'})
        return css+'.ad .text{font-family:Pretendard,HanjangNoto!important}',key
    monkeypatch.setattr(fonts,'load_fonts',isolated)
    app.state.design_store.executor=render_templates
    p,s=generate(designs,'emotional');candidate=s['candidates'][0]
    assert c.post(p+'/ranking',headers=h,json=snap(s)).status_code==200  # explicit MockRanker fixture
    change={'headline':'힣 한글 새 제목','body':'가 Café 새 본문','cta':'새롭게 만나보세요'}
    url=p+'/candidates/'+candidate['candidate_id']
    assert c.patch(url,headers=h,json={**snap(s),'expected_asset_id':candidate['png']['asset_id'],
                                     'copy':change,'price_text':'6,500원'}).status_code==202
    latest=c.get(p,headers=h).json()
    assert latest['status']=='completed' and latest['revision']==s['revision']+1
    assert latest['candidates'][0]['copy']==change and latest['ranking'] is None
    assert latest['style_snapshot']==s['style_snapshot']
    assert [v['png']['asset_id'] for v in latest['candidates'][1:]]==[v['png']['asset_id'] for v in s['candidates'][1:]]
    assert c.get(url+'/download',headers=h,params={'format':'png',**snap(s)}).status_code==409
    assert c.get(url+'/download',headers=h,params={'format':'png',**snap(latest)}).status_code==200
    measurement=app.state.upload_store.records[m['job_id']].design_sets['emotional'].measurements[candidate['candidate_id']]
    assert not measurement['invalid']
    assert all(f['isCustomFont'] for t in measurement['text'] for f in t['actual_fonts'])
