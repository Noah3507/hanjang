from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import os

from PIL import Image,ImageDraw
import pytest
from app.services.template_v3 import TemplateInput, REGISTRY, render_templates, BOLD_HASH, ROOT
from app.services.render_execution import RenderFailure


def data():
    return TemplateInput('테스트 상점','상품 이름',' 10,500원 ','오늘의 선택','구성을 확인하세요.','상품 보기')


def photo():
    s=BytesIO();image=Image.new('RGBA',(400,700));ImageDraw.Draw(image).rounded_rectangle((100,60,300,640),radius=20,fill='white');image.save(s,'PNG');return s.getvalue()


def test_registry_and_real_bold():
    assert len(REGISTRY)==16 and all(v['implemented'] for v in REGISTRY.values())
    assert sha256((ROOT/'templates/fonts/NotoSansKR-Bold.otf').read_bytes()).hexdigest()==BOLD_HASH
    from fontTools.ttLib import TTFont
    with TTFont(ROOT/'templates/fonts/NotoSansKR-Bold.otf') as f:
        assert f['OS/2'].usWeightClass==700


@pytest.mark.parametrize('ids',[[],['price_a','price_a'],['../price_a'],['brand_e']])
def test_invalid_template(ids):
    with pytest.raises(RenderFailure) as e:render_templates(data(),photo(),ids)
    assert e.value.code=='RENDER_INVALID_TEMPLATE'


def test_unsupported_glyph_and_bad_image():
    with pytest.raises(RenderFailure) as e:render_templates(replace(data(),product_name='🧪'),photo())
    assert e.value.code=='RENDER_UNSUPPORTED_GLYPH'
    with pytest.raises(RenderFailure) as e:render_templates(data(),b'not an image')
    assert e.value.code=='RENDER_INVALID_IMAGE'


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_four_real_renders_exact_text_optional_claims():
    original=data();rows=render_templates(original,photo())
    assert len({r['candidate_id'] for r in rows})==4
    assert len({r['asset_id'] for r in rows})==4
    for row in rows:
        assert row['strategy']=='price' and row['revision']==1
        with Image.open(BytesIO(row['png'])) as im:assert im.size==(1080,1350) and im.mode=='RGB'
        texts={t['field']:t for t in row['measurement']['text']}
        for field in ('store_name','product_name','price_text','headline','body','cta'):
            assert texts[field]['text']==getattr(original,field)
            assert texts[field]['actual_fonts'] and not texts[field]['overflow']
        assert not {'original_price','discount_text','promotion_text','period_text'} & texts.keys()
        assert row['diagnostics'] and not row['measurement']['text_collisions']
        assert row['diagnostics']['coverage']!='unavailable'
        assert all(r['coverage']=='complete' for r in row['diagnostics']['rules'] if r['rule_id']!='contrast')


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_long_final_text_fails_without_truncating():
    original=replace(data(),product_name='아주 긴 상품 이름 '*100)
    with pytest.raises(RenderFailure) as e:render_templates(original,photo())
    assert e.value.code=='RENDER_LAYOUT_OVERFLOW'
    assert original.product_name=='아주 긴 상품 이름 '*100


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_promotion_and_long_mixed_text():
    original=replace(data(),product_name='아침과 저녁에 사용하는 데일리 보습 로션',
        body='매일 사용하는 상품입니다. 구성과 가격을 확인하고 나에게 맞는 상품을 선택하세요.',
        original_price='15,000원',discount_text='30%',promotion_text='테스트 행사',period_text='2026.11.16–2026.11.20')
    rows=render_templates(original,photo())
    for row in rows:
        texts={t['field']:t['text'] for t in row['measurement']['text']}
        assert texts=={k:v for k,v in original.__dict__.items() if v}
        assert not row['measurement']['text_collisions']


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_all_sixteen_mixed_text_and_hidden_price():
    for strategy in ('emotional','price','brand','visual'):
        original=replace(data(),product_name='로션 A&B (2+1)',price_text='',headline='일상에 더하는 선택')
        for row in render_templates(original,photo(),[strategy+'_'+c for c in 'abcd']):
            assert row['strategy']==strategy
            texts={t['field']:t for t in row['measurement']['text']}
            assert texts['product_name']['text']==original.product_name
            assert 'price_text' not in texts
            assert not row['measurement']['invalid']


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_fade_promotion_has_measured_contrast_backplate():
    original=replace(data(),original_price='15,000원',discount_text='30%',promotion_text='테스트 행사')
    row=render_templates(original,photo(),['emotional_b'])[0]
    contrast=next(r for r in row['diagnostics']['rules'] if r['rule_id']=='contrast')
    assert not any(i['status']=='problem' for i in contrast['measured_value']['items'])
    measured=next(t for t in row['measurement']['text'] if t['field']=='discount_text')['contrast_evidence']
    assert measured['status']=='verified' and measured['background_rgb']==[38,61,46]


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS')!='1',reason='Explicit installed Chromium opt-in')
def test_long_product_fits_even_when_template_font_is_important():
    # Long enough to need shrinking with Pretendard (narrower than Noto Sans).
    original=replace(data(),product_name='나만의 시간에 사용하는 데일리 보습 로션')
    row=render_templates(original,photo(),['brand_a'])[0]
    measured=next(t for t in row['measurement']['text'] if t['field']=='product_name')
    assert measured['text']==original.product_name and not measured['overflow']
    assert measured['font_size_px']<70 and measured['font_size_px']>=70*.76-.01
