"""Empty copy fields give their space to the photo and the remaining text (templates/v3, B).

Real copy often leaves the body or CTA empty. The page is flagged with .no-body / .no-cta and the
templates lay out without the blank bands. The static checks run everywhere; the render checks need
Chromium (RUN_RENDER_TESTS=1).
"""
import os
import re
from io import BytesIO
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.template_v3 import REGISTRY, TemplateInput

ROOT = Path(__file__).resolve().parents[2]
QUALITY = (ROOT / 'templates/v3/quality.css').read_text(encoding='utf-8')


def main_classes(template_id, data):
    env = Environment(loader=FileSystemLoader(ROOT / 'templates/v3'), undefined=StrictUndefined)
    html = env.get_template(template_id + '.html').render(css='', data=data, photo='', photo_fit='contain',
                                                         transparent=True, template_id=template_id)
    return re.search(r'<main class="([^"]+)"', html).group(1).split()


@pytest.mark.parametrize('template_id', sorted(REGISTRY))
def test_empty_fields_are_flagged_and_the_template_id_stays_second(template_id):
    full = TemplateInput('가게', '상품', '1,000원', '제목', '본문', '버튼')
    empty = TemplateInput('가게', '상품', '1,000원', '제목', ' ', '')
    assert main_classes(template_id, full) == ['ad', template_id]
    # The render worker reads the template id as classList[1].
    assert main_classes(template_id, empty) == ['ad', template_id, 'no-body', 'no-cta']


def test_fill_rules_never_lower_a_font_size():
    block = QUALITY[QUALITY.index('/* Fill (2026-11-27)'):QUALITY.index('/* Quality 2 (2026-11-28)')]
    sizes = [int(v) for v in re.findall(r'font-size:(\d+)px', block)]
    assert sizes and min(sizes) >= 44  # only lone headlines grow; nothing shrinks


def photo_png():
    from PIL import Image, ImageDraw
    buffer = BytesIO()
    image = Image.new('RGBA', (600, 400))
    ImageDraw.Draw(image).ellipse((20, 20, 580, 380), fill='white')
    image.save(buffer, 'PNG')
    return buffer.getvalue()


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
def test_photo_takes_the_space_of_an_empty_body():
    from app.services.template_v3 import render_templates
    ids = sorted(REGISTRY)
    png = photo_png()
    full = render_templates(TemplateInput('골목반점', '짜장면', '7,000원', '오늘의 선택', '구성을 확인하세요.', '주문하기'),
                            png, ids, timeout=240)
    empty = render_templates(TemplateInput('골목반점', '짜장면', '7,000원', '오늘의 선택', '', ''), png, ids, timeout=240)
    grown = {f['template_id'] for f, e in zip(full, empty)
             if e['measurement']['photo_frame']['height'] > f['measurement']['photo_frame']['height']}
    assert {'emotional_a', 'emotional_b', 'emotional_d', 'brand_b', 'price_c',
            'visual_a', 'visual_b', 'visual_c', 'visual_d'} <= grown


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
@pytest.mark.parametrize('data', [
    TemplateInput('테스트 상점', '상품 이름', '10,500원', '오늘의 선택', '', '', discount_text='30%',
                  original_price='15,000원', promotion_text='이번 주 행사', period_text='2026.11.23 ~ 11.29'),
    TemplateInput('골목반점', '짜장면', '7,000원', '오늘은 입가에 검은 소스 묻혀도 괜찮은 날, 한 그릇 더', '', ''),
    TemplateInput('달콤한 하루 수제 디저트 제과점', '딸기 생크림 홀케이크 2호 사이즈', '35,000원', '오늘의 선택', '', ''),
    TemplateInput('한장 테스트 가게', '나만의 시간에 사용하는 데일리 보습 로션', '12,000원', '오늘의 선택', '구성을 확인하세요.', '상품 보기'),
], ids=['empty-with-promotion', 'empty-long-headline', 'empty-long-names', 'long-product-name'])
def test_every_template_still_fits(data):
    from app.services.template_v3 import render_templates
    rows = render_templates(data, photo_png(), sorted(REGISTRY), timeout=240)
    assert all(r['measurement']['text_collisions'] == [] for r in rows)
