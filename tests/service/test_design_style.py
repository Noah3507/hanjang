"""design_style.py: kind recognition, three style layers, contrast and template facts."""
import re
from itertools import product
from pathlib import Path

import pytest

from app.services.design_style import (KINDS, MOODS, ROLES, STYLE_VERSION, TEMPLATES, TONES, Style, StyleInput,
                                       accent_candidates, kind_from_name, ratio, recognize_kind, resolve_style, rgb,
                                       text_pairs)
from app.services.diagnostics_engine import CONTRAST_MINIMUM
from app.services.template_v3 import REGISTRY

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name, kind', [
    ('짜장면', 'noodle_soup'), ('해물 우동면', 'noodle_soup'), ('훠궈', 'noodle_soup'), ('소고기 샤브샤브', 'noodle_soup'), ('마라탕', 'noodle_soup'), ('김치찌개', 'noodle_soup'),
    ('후라이드 치킨', 'fried_grill'), ('탕수육', 'fried_grill'), ('등심 돈가스', 'fried_grill'), ('삼겹살', 'fried_grill'),
    ('치킨 덮밥', 'rice_meal'), ('참치 김밥', 'rice_meal'), ('면세점 도시락', 'rice_meal'), ('제육 덮밥', 'rice_meal'),
    ('연어 포케', 'fresh_light'), ('리코타 샐러드', 'fresh_light'), ('에그 샌드위치', 'fresh_light'),
    ('딸기 케이크', 'dessert_bakery'), ('소금빵', 'dessert_bakery'), ('팥빙수', 'dessert_bakery'), ('커피 케이크', 'dessert_bakery'),
    ('아이스 아메리카노', 'drink'), ('카페라떼', 'drink'), ('녹차', 'drink'), ('녹차 라떼', 'drink'), ('레몬 에이드', 'drink'),
    ('차슈 라멘', 'noodle_soup'), ('차돌 짬뽕', 'noodle_soup'), ('빵가루 치킨', 'fried_grill'),
])
def test_kind_from_name(name, kind):
    assert kind_from_name(name) == kind


@pytest.mark.parametrize('name', ['차슈', '차돌박이', '면도기', '탕비실 세트', '자동차 방향제', '수제 키링', '', '   '])
def test_short_words_do_not_misfire(name):
    assert kind_from_name(name) is None


def test_recognition_priority():
    assert recognize_kind('짜장면', user_kind='drink') == ('drink', 'user')
    assert recognize_kind('짜장면', user_kind='made_up') == ('noodle_soup', 'name')
    assert recognize_kind('짜장면', 'drink', 0.5) == ('noodle_soup', 'name')
    assert recognize_kind('시그니처 메뉴', 'drink', 0.5) == ('drink', 'clip')
    assert recognize_kind('시그니처 메뉴', 'dessert', 0.5) == ('dessert_bakery', 'clip')
    assert recognize_kind('시그니처 메뉴', 'drink', 0.0) == ('general_food', 'default')
    assert recognize_kind('시그니처 메뉴', 'drink', None) == ('general_food', 'default')
    assert recognize_kind('시그니처 메뉴', 'unknown', 0.5) == ('general_food', 'default')
    assert recognize_kind('키링', 'nonfood', 0.5) == ('nonfood', 'clip')


def test_templates_table_covers_the_registry():
    assert set(TEMPLATES) == set(REGISTRY)


def css_fallbacks():
    css = ''.join((ROOT / 'templates/v3' / n).read_text(encoding='utf-8') for n in ('price.css', 'collection.css', 'quality.css'))
    rules = [(' '.join(s.split()), body) for s, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)]
    return css, rules


def luminance_is_light(hex_colour):
    full = '#' + ''.join(ch * 2 for ch in hex_colour[1:]) if len(hex_colour) == 4 else hex_colour
    return ratio(rgb(full.upper() if full != 'white' else '#FFFFFF'), (0, 0, 0)) > 7


def fallback(rules, selectors, role):
    """Last fallback for role among rules whose selector is exactly one of selectors."""
    value = None
    for selector, body in rules:
        if selector in selectors:
            for m in re.finditer(r'(?<![\w-])(?:background|border|border-top):[^;]*var\(--%s,([^()]+?)\)' % re.escape(role), body):
                value = m.group(1).strip()
    return value


@pytest.mark.parametrize('template_id', sorted(TEMPLATES))
def test_template_polarity_matches_css(template_id):
    _, rules = css_fallbacks()
    family = template_id.split('_')[0]
    bg = fallback(rules, {'.ad', f'.{template_id}'}, 'bg')
    photo = fallback(rules, {'.photo', '.ad:is([class*=emotional_],[class*=brand_],[class*=visual_]) .photo' if family != 'price' else '.photo',
                             f'.{template_id} .photo'}, 'photo-bg')
    colour = lambda v: '#FFFFFF' if v == 'white' else v
    polarity, photo_polarity, *_ = TEMPLATES[template_id]
    assert ('light' if luminance_is_light(colour(bg)) else 'dark') == polarity
    assert ('light' if luminance_is_light(colour(photo)) else 'dark') == photo_polarity


def test_surface_polarity_matches_css():
    _, rules = css_fallbacks()
    colour = lambda v: '#FFFFFF' if v == 'white' else v
    price_bands = {fallback(rules, {s}, 'surface') for s in ('header', 'footer')}
    assert {luminance_is_light(colour(v)) for v in price_bands} == {False}
    assert {TEMPLATES[t][2] for t in TEMPLATES if t.startswith('price_')} == {'dark'}
    assert luminance_is_light(colour(fallback(rules, {'.visual_b .decoration'}, 'surface')))
    assert TEMPLATES['visual_b'][2] == 'light'
    # Photo frames share the surface polarity (white polaroid frame on visual_b, dark border on price).
    for template_id, selectors in {'visual_b': {'.visual_b .photo'}, 'emotional_d': {'.emotional_d .photo'},
                                   'brand_c': {'.brand_c .photo'}, 'price_a': {'.photo'}}.items():
        frame = fallback(rules, selectors, 'frame')
        assert ('light' if luminance_is_light(colour(frame)) else 'dark') == TEMPLATES[template_id][2], template_id


def test_accent_text_rules_match_css():
    css, rules = css_fallbacks()
    accent_text = {s for s, body in rules if re.search(r'(?<![\w-])color:var\(--accent,', body)}
    assert accent_text == {'.period', '.price_c .price', '.brand_a .product'}
    assert re.search(r'\.ad:is\(\[class\*=emotional_\],\[class\*=brand_\],\[class\*=visual_\]\) \.period\{[^}]*color:inherit', css)
    # The period sits in the footer (surface) of every price template; price_b/c/d extend price_a.
    for name in ('price_b', 'price_c'):
        assert "{% extends 'price_a.html' %}" in (ROOT / f'templates/v3/{name}.html').read_text(encoding='utf-8')
    assert 'class="text period"' in (ROOT / 'templates/v3/price_a.html').read_text(encoding='utf-8')
    assert {t for t, facts in TEMPLATES.items() if 'surface' in facts[3]} == {'price_a', 'price_b', 'price_c', 'price_d'}
    assert {t for t, facts in TEMPLATES.items() if 'bg' in facts[3]} == {'price_c', 'brand_a'}


PALETTES = [(), (('#C8102E', 0.4), ('#F2F2F2', 0.5)), (('#F4C542', 0.3),), (('#2E7D32', 0.2), ('#6D4C41', 0.6)),
            (('#111111', 0.9),), (('#FFFFFF', 0.9),), (('#1565C0', 0.12), ('#FF80AB', 0.5)),
            (('#7B1FA2', 0.5),), (('#00ACC1', 0.3), ('#FFEB3B', 0.3)), (('#3E2A1E', 0.7), ('#E8E0D0', 0.3))]
NAMES = ['짜장면', '치킨', '김밥', '샐러드', '케이크', '아메리카노', '키링', '오늘의 메뉴']


@pytest.mark.parametrize('template_id, mood', list(product(sorted(TEMPLATES), MOODS)))
def test_every_text_pair_is_readable(template_id, mood):
    for name, palette in product(NAMES, PALETTES):
        style = resolve_style(StyleInput(template_id, mood, name, palette))
        if not style.variables:
            continue
        v = {k: rgb(c) for k, c in style.variables.items()}
        for fg, bg in text_pairs(template_id):
            assert ratio(v[fg], v[bg]) >= CONTRAST_MINIMUM, (name, palette, fg, bg, style.variables)


def test_values_are_safe_and_complete():
    style = resolve_style(StyleInput('price_a', 'warm', '짜장면', (('#C8102E', 0.4),)))
    assert style.version == STYLE_VERSION and style.kind == 'noodle_soup' and style.kind_source == 'name'
    assert set(style.variables) == set(ROLES)
    assert all(re.fullmatch(r'#[0-9A-F]{6}', v) for v in style.variables.values())
    assert re.fullmatch(r'\.ad\{(--[a-z-]+:#[0-9A-F]{6};)*--[a-z-]+:#[0-9A-F]{6}\}', style.css())


def test_unknown_inputs_give_no_variables():
    for data in (StyleInput('price_z', 'warm', '짜장면', (('#C8102E', 0.4),)), StyleInput('price_a', 'gloomy', '짜장면'),
                 StyleInput('price_a', 'warm', '오늘의 메뉴'), StyleInput('price_a', 'warm', '키링', (), 'nonfood', 0.5),
                 StyleInput('price_a', 'warm', '오늘의 메뉴', (('#F2F2F2', 0.9), ('#202020', 0.1)))):
        style = resolve_style(data)
        assert style.variables == {} and style.css() == '' and style.background_source == 'none'
    assert resolve_style(StyleInput('price_a', 'warm', '키링', (), 'nonfood', 0.5)).kind == 'nonfood'


def test_background_hue_comes_from_the_photo_when_it_has_a_clear_colour():
    from app.services.design_style import delta_e
    lemon = resolve_style(StyleInput('price_a', 'warm', '레몬 에이드', (('#F4D03F', 0.5), ('#FFFFFF', 0.4))))
    latte = resolve_style(StyleInput('price_a', 'warm', '카페라떼', (('#A0703C', 0.5), ('#FFFFFF', 0.4))))
    assert lemon.kind == latte.kind == 'drink'
    assert lemon.background_source == latte.background_source == 'photo'
    berry = resolve_style(StyleInput('price_a', 'warm', '블루베리 스무디', (('#5B3A8C', 0.5),)))
    assert delta_e(rgb(lemon.variables['bg']), rgb(latte.variables['bg'])) >= 5   # same kind, neighbouring hues
    assert delta_e(rgb(lemon.variables['bg']), rgb(berry.variables['bg'])) >= 20  # same kind, far apart hues


def test_photos_without_a_clear_colour_use_the_kind_table():
    for palette in [(), (('#FFFFFF', 0.6), ('#1A1A1A', 0.4)), (('#2B1D14', 0.7), ('#F2EFE8', 0.3))]:  # black sauce, white plate
        style = resolve_style(StyleInput('price_a', 'warm', '짜장면', palette))
        assert style.background_source == 'kind'
        assert style.variables['bg'] == resolve_style(StyleInput('price_a', 'warm', '짜장면')).variables['bg']


def test_unknown_names_still_follow_a_clear_photo_colour():
    style = resolve_style(StyleInput('emotional_b', 'warm', '시그니처 메뉴', (('#7B1FA2', 0.5),)))
    assert style.kind == 'general_food' and style.background_source == 'photo' and set(style.variables) == set(ROLES)


def test_kind_still_pulls_the_hue():
    from app.services.design_style import _hue
    photo = (('#4CAF50', 0.5),)  # the same green photo
    salad = rgb(resolve_style(StyleInput('price_a', 'warm', '샐러드', photo)).variables['bg'])
    cake = rgb(resolve_style(StyleInput('price_a', 'warm', '케이크', photo)).variables['bg'])
    assert salad != cake  # 30 % of the hue comes from the kind
    assert abs(_hue(salad) - _hue(rgb('#4CAF50'))) < abs(_hue(cake) - _hue(rgb('#4CAF50')))


def test_mix_hue_wraps_around_red():
    from app.services.design_style import mix_hue
    assert mix_hue(0.97, 0.03, 0.5) == pytest.approx(0.0, abs=1e-9) or mix_hue(0.97, 0.03, 0.5) == pytest.approx(1.0, abs=1e-9)
    assert mix_hue(0.2, None, 0.7) == 0.2


def test_same_input_same_output():
    data = StyleInput('emotional_b', 'vivid', '딸기 케이크', (('#E91E63', 0.3), ('#FFFFFF', 0.5)))
    assert resolve_style(data) == resolve_style(data)
    assert resolve_style(data).css() == resolve_style(StyleInput(*data.__dict__.values())).css()


def test_accent_from_photo():
    assert accent_candidates((('#F2F2F2', 0.6), ('#C8102E', 0.07), ('#E67E22', 0.2), ('bad', 0.5), ('#2E7D32', True))) == [rgb('#E67E22')]
    photo = resolve_style(StyleInput('price_b', 'warm', '치킨', (('#F5A623', 0.3),)))
    assert photo.accent_source == 'photo' and photo.variables['accent'] == '#F5A623'
    none = resolve_style(StyleInput('price_b', 'warm', '치킨', (('#F2F2F2', 0.9),)))
    assert none.accent_source == 'kind' and none.background_source == 'kind'


@pytest.mark.parametrize('mood', MOODS)
def test_kinds_get_clearly_different_backgrounds(mood):
    """Without a photo colour, kinds still differ on the same template (baseline: delta E 0).
    Neutral-strength templates (grey/white/black today) differ less by design, so the floor is lower."""
    from itertools import combinations
    from statistics import median
    from app.services.design_style import delta_e
    names = dict(zip(TONES, ['짜장면', '치킨', '김밥', '샐러드', '케이크', '아메리카노']))
    distances = []
    for template_id in TEMPLATES:
        bg = {k: rgb(resolve_style(StyleInput(template_id, mood, n)).variables['bg']) for k, n in names.items()}
        distances += [delta_e(bg[a], bg[b]) for a, b in combinations(bg, 2)]
    assert min(distances) >= 2.5
    assert median(distances) >= 12


def test_level_matches_current_template_colour_strength():
    """Bold yellow/lime, pale cream, coloured deep green and neutral grey/black/white templates keep their strength."""
    _, rules = css_fallbacks()
    from app.services.design_style import saturation
    for template_id, facts in TEMPLATES.items():
        bg = fallback(rules, {'.ad', f'.{template_id}'}, 'bg')
        c = rgb('#' + ''.join(ch * 2 for ch in bg[1:]).upper() if len(bg) == 4 else bg.upper())
        level = facts[4]
        chroma = (max(c) - min(c)) / 255  # HSV saturation overstates very dark colours
        if level == 'bold':
            assert chroma > 0.4, template_id
        elif level in ('pale', 'coloured'):
            assert 0.065 < chroma <= 0.4, template_id
        else:
            assert chroma <= 0.065, template_id


def test_a_products_four_drafts_keep_different_strengths():
    from app.services.design_style import delta_e
    styles = {t: rgb(resolve_style(StyleInput(t, 'warm', '레몬 에이드', (('#F4D03F', 0.5),))).variables['bg'])
              for t in ('price_a', 'price_d', 'brand_b', 'brand_d')}
    assert delta_e(styles['price_a'], styles['price_d']) >= 15   # bold vs neutral
    assert delta_e(styles['brand_b'], styles['brand_d']) >= 15   # pale vs bold


def test_price_b_and_c_no_longer_share_a_style():
    for name, palette in [('레몬 에이드', (('#F4D03F', 0.5),)), ('짜장면', ()), ('딸기 케이크', (('#D8314F', 0.5),))]:
        b = resolve_style(StyleInput('price_b', 'warm', name, palette)).variables
        c = resolve_style(StyleInput('price_c', 'warm', name, palette)).variables
        assert b['bg'] != c['bg'], name


def test_style_is_a_plain_value():
    style = resolve_style(StyleInput('visual_c', 'premium', '아메리카노'))
    assert isinstance(style, Style) and style.kind in KINDS
