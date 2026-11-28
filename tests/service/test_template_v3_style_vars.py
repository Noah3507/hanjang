"""Template colours are CSS variables whose fallbacks are the original colours.

Until design_style.py supplies values, every ad must render exactly as before.
The static checks run everywhere; the pixel check needs Chromium (RUN_RENDER_TESTS=1).
"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS = [ROOT / 'templates/v3' / name for name in ('price.css', 'collection.css', 'quality.css')]
# Colour roles a style may set. Keep in step with the design doc; removing or renaming one needs A's agreement.
ROLES = {'bg', 'ink', 'ink-soft', 'accent', 'accent-ink', 'surface', 'surface-ink', 'frame', 'photo-bg', 'decor'}
VAR = re.compile(r'var\(--([a-z-]+),([^()]+?)\)')
# Layout variables (not colours) used inside the templates' own CSS; they have no fallback by design.
LAYOUT = re.compile(r'var\(--stack-top\)')
LITERAL = re.compile(r'#[0-9a-fA-F]{3,6}\b|\bwhite\b')


def resolve(css: str) -> str:
    """The CSS a browser applies when no colour variable is set."""
    return VAR.sub(lambda m: m.group(2), css)


@pytest.mark.parametrize('path', CSS, ids=lambda p: p.name)
def test_every_colour_is_a_known_role_with_a_literal_fallback(path):
    css = path.read_text(encoding='utf-8')
    uses = VAR.findall(css)
    assert uses, 'no colour variables found'
    assert {name for name, _ in uses} <= ROLES
    assert all(LITERAL.fullmatch(fallback.strip()) for _, fallback in uses)
    assert 'var(' not in LAYOUT.sub('', resolve(css))


@pytest.mark.parametrize('path', CSS, ids=lambda p: p.name)
def test_no_colour_is_left_outside_a_variable(path):
    css = VAR.sub('', path.read_text(encoding='utf-8')).replace('white-space', '')
    assert not LITERAL.search(css)


def test_templates_do_not_define_the_variables_themselves():
    """Only design_style.py sets the roles; a template that set one would hide the fallback."""
    for path in CSS + sorted((ROOT / 'templates/v3').glob('*.html')):
        assert not re.search(r'--(%s)\s*:' % '|'.join(map(re.escape, ROLES)), path.read_text(encoding='utf-8'))


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
def test_all_sixteen_render_pixel_identical_to_the_fallback_css(monkeypatch):
    from io import BytesIO
    from PIL import Image, ImageDraw
    from app.services import template_v3
    from app.services.template_v3 import REGISTRY, TemplateInput, render_templates

    data = TemplateInput('테스트 상점', '상품 이름', '10,500원', '오늘의 선택', '구성을 확인하세요.', '상품 보기',
                         discount_text='30%', original_price='15,000원', promotion_text='이번 주 행사', period_text='2026.11.23 ~ 11.29')
    buffer = BytesIO()
    image = Image.new('RGBA', (400, 700))
    ImageDraw.Draw(image).rounded_rectangle((100, 60, 300, 640), radius=20, fill='white')
    image.save(buffer, 'PNG')
    ids = sorted(REGISTRY)

    def pixels(rows):
        return {r['template_id']: Image.open(BytesIO(r['png'])).convert('RGB').tobytes() for r in rows}

    with_vars = pixels(render_templates(data, buffer.getvalue(), ids, timeout=240))
    original_read = Path.read_text

    def fallback_read(self, *args, **kwargs):
        text = original_read(self, *args, **kwargs)
        return resolve(text) if self.suffix == '.css' and self.parent.name == 'v3' else text

    monkeypatch.setattr(template_v3.Path, 'read_text', fallback_read)
    without_vars = pixels(render_templates(data, buffer.getvalue(), ids, timeout=240))
    assert [t for t in ids if with_vars[t] != without_vars[t]] == []
