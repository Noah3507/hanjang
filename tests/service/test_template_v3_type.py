"""Template typography: original draft fonts per strategy and readable starting sizes."""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / 'templates/v3/quality.css').read_text(encoding='utf-8')
# A's candidate role thresholds (PR #68); not the operating diagnostic yet.
CANDIDATE = {'headline': 36, 'price_text': 36, 'product_name': 32, 'body': 28, 'cta': 28, 'store_name': 28}
# The visual body slot holds two lines; this longest real body needs three at 28px and shrinks.
# Copy length limits per template (limits.json) will keep bodies within two lines.
KNOWN_LONG_BODY = {('visual_a', 'body'), ('visual_c', 'body'), ('visual_d', 'body')}
FAMILY = {'emotional': 'Noto Serif KR', 'price': 'Pretendard', 'brand': 'Pretendard', 'visual': 'HanjangNoto'}


def rendered_names(family):
    """Pages carry subsets renamed 'HanjangSubset' + the asset's sha256 prefix (render_fonts, PR #71)."""
    import json
    from app.services.render_fonts import _subset_name
    manifest = json.loads((ROOT / 'backend/assets/fonts/manifest.json').read_text(encoding='utf-8'))
    entries = manifest['faces']
    names = {_subset_name(entry['sha256']) for entry in entries if entry['family'] == family}
    assert names, family
    return names


def test_strategy_fonts_are_declared_with_fallback():
    assert ".ad[class*=emotional_]{font-family:'Noto Serif KR',HanjangNoto,sans-serif}" in CSS
    assert '.ad[class*=price_],.ad[class*=brand_]{font-family:Pretendard,HanjangNoto,sans-serif}' in CSS
    assert not re.search(r'visual_[^{]*\{[^}]*font-family', CSS)  # visual keeps Noto Sans


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
def test_long_real_copy_stays_readable_in_all_sixteen():
    from io import BytesIO
    from PIL import Image, ImageDraw
    from app.services.template_v3 import TemplateInput, render_templates
    # Actual v6 LLM copy (docs/COPY_QUALITY_PHASE2_RESULTS.md), the longest bodies seen so far.
    copy = {'emotional': ('점심에 생각나는 짜장면', '따뜻한 분위기 속에서 짜장면 한 그릇이 든든하게 들어옵니다. 골목반점에서 편하게 한 끼 이어가세요.', '주문하기'),
            'price': ('짜장면 7,000원', '7,000원에 짜장면을 고를 수 있어 식사 메뉴로 부담 없이 맞춥니다. 골목반점에서 오늘 메뉴를 정해보세요.', '메뉴 보기'),
            'visual': ('윤기 도는 짜장면', '윤기 있는 표면과 부드러운 면발이 먼저 보이는 한 그릇입니다. 보기만 해도 익숙한 맛이 떠오릅니다.', '맛보기'),
            'brand': ('골목반점 짜장면', '골목반점 이름 그대로 골목에서 떠올리기 쉬운 짜장면입니다. 익숙한 한 끼로 자연스럽게 찾게 됩니다.', '들러보기')}
    image = Image.new('RGBA', (800, 800))
    ImageDraw.Draw(image).ellipse((150, 220, 650, 630), fill=(200, 120, 42, 255))
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    small = []
    expected = {strategy: rendered_names(family) for strategy, family in FAMILY.items()}
    for strategy, (headline, body, cta) in copy.items():
        rows = render_templates(TemplateInput('골목반점', '짜장면', '7,000원', headline, body, cta), buffer.getvalue(),
                                [f'{strategy}_{c}' for c in 'abcd'], timeout=300)
        for row in rows:
            for text in row['measurement']['text']:
                assert not text['overflow'], (row['template_id'], text['field'])
                fonts = {f['familyName'] for f in text.get('actual_fonts') or []}
                assert fonts & expected[strategy], (row['template_id'], fonts)
                floor = 24 if (row['template_id'], text['field']) in KNOWN_LONG_BODY else CANDIDATE.get(text['field'])
                if floor and text['font_size_px'] < floor:
                    small.append((row['template_id'], text['field'], text['font_size_px']))
    assert small == []
