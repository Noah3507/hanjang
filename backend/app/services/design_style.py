"""Per-product ad style: product kind + photo colour -> base tone, mood -> direction, photo palette -> accent.

The background hue mixes the photo's main colour (70 %) with the product kind's hue (30 %);
lightness and saturation come from the template (light templates stay pale, dark ones deep),
so the product still stands out and text stays readable. A photo without a usable colour
(white plate, black sauce, grey) falls back to the kind's table colours.

Owned by B. A pure function: no files, network, clock or randomness, so the same
input always gives the same CSS variables. Only the colour roles that the v3
templates read as var(--role, current colour) are produced; an unknown template,
mood or a general/non-food product gives no variables, so the template keeps its
current colours. Every text/background pair is checked with the same WCAG formula
as the readability diagnostics.
"""
from __future__ import annotations

import colorsys
import math
import re
from dataclasses import dataclass, field

from app.services.diagnostics_engine import CONTRAST_MINIMUM, contrast

STYLE_VERSION = 'design-style-v4'
KINDS = ('noodle_soup', 'fried_grill', 'rice_meal', 'fresh_light', 'dessert_bakery', 'drink', 'nonfood', 'general_food')
MOODS = ('warm', 'minimal', 'vivid', 'premium')
ROLES = ('bg', 'ink', 'ink-soft', 'accent', 'accent-ink', 'surface', 'surface-ink', 'frame', 'photo-bg', 'decor')

# ---------- decision 1: product kind ----------

WORDS = {
    'noodle_soup': ('면', '짜장', '짬뽕', '라멘', '라면', '소바', '우동', '국수', '냉면', '파스타', '스파게티',
                    '찌개', '탕', '국밥', '국', '수제비', '쌀국수', '전골', '훠궈', '샤브샤브'),
    'fried_grill': ('치킨', '튀김', '돈까스', '돈가스', '까스', '가스', '구이', '고기', '삼겹', '꼬치', '갈비',
                    '스테이크', '닭강정', '족발', '보쌈', '바베큐', '바비큐', '탕수육', '버거', '햄버거'),
    'rice_meal': ('밥', '덮밥', '비빔', '김밥', '주먹밥', '정식', '도시락', '볶음밥', '리조또', '오므라이스',
                  '카레', '돈부리', '백반'),
    'fresh_light': ('샐러드', '포케', '샌드위치', '샌드', '요거트', '과일', '브리또', '랩'),
    'dessert_bakery': ('케이크', '빵', '쿠키', '마카롱', '크로플', '도넛', '타르트', '빙수', '와플', '푸딩',
                       '아이스크림', '젤라또', '베이글', '크루아상', '스콘', '머핀', '휘낭시에', '마들렌',
                       '떡', '사탕', '초콜릿'),
    'drink': ('커피', '라떼', '아메리카노', '차', '에이드', '스무디', '주스', '티', '콜드브루', '에스프레소',
              '카푸치노', '모카', '프라푸치노', '쉐이크', '밀크티', '음료'),
}
# Words that contain a dictionary word but mean something else; None = not a product word.
EXCEPTIONS = {'탕수육': 'fried_grill', '사탕': 'dessert_bakery', '차슈': None, '차돌': None, '설탕': None,
              '자동차': None, '주차': None, '세차': None, '가스레인지': None, '랩탑': None, '국산': None,
              '국내산': None, '티셔츠': None, '면세': None}
CLIP_KINDS = {'food': 'general_food', 'drink': 'drink', 'dessert': 'dessert_bakery', 'nonfood': 'nonfood'}
# Placeholder until A picks the threshold from real analysis results (design doc, decision 1).
CLIP_MIN_MARGIN = 0.02


def _matches(name: str) -> list[tuple[int, int, str]]:
    """(start, end, kind) for every accepted word, after the matching rules of decision 1."""
    found = []
    for word, kind in EXCEPTIONS.items():
        for m in re.finditer(re.escape(word), name):
            found.append((m.start(), m.end(), kind, True))
    for kind, words in WORDS.items():
        for word in words:
            for m in re.finditer(re.escape(word), name):
                found.append((m.start(), m.end(), kind, False))
    last_end = len(name.rstrip())
    accepted = []
    # Exceptions first, then longer words; a span inside an accepted span is ignored.
    for start, end, kind, exception in sorted(found, key=lambda f: (not f[3], -(f[1] - f[0]), f[0])):
        if any(s <= start and end <= e for s, e, _ in accepted):
            continue
        if not exception and end - start == 1 and end != last_end:
            continue  # one-character words count only at the very end of the name
        accepted.append((start, end, kind))
    return [a for a in accepted if a[2] is not None]


def kind_from_name(product_name: str) -> str | None:
    name = ' '.join(str(product_name).split())
    matches = _matches(name)
    if not matches:
        return None
    return max(matches, key=lambda m: (m[0], m[1] - m[0]))[2]  # the word that comes last wins


def recognize_kind(product_name: str, kind_hint: str | None = None, kind_hint_margin: float | None = None,
                   user_kind: str | None = None) -> tuple[str, str]:
    """(kind, source): user choice > product-name dictionary > CLIP hint > default."""
    if user_kind in KINDS:
        return user_kind, 'user'
    named = kind_from_name(product_name or '')
    if named:
        return named, 'name'
    if (kind_hint in CLIP_KINDS and isinstance(kind_hint_margin, (int, float))
            and not isinstance(kind_hint_margin, bool) and kind_hint_margin >= CLIP_MIN_MARGIN):
        return CLIP_KINDS[kind_hint], 'clip'
    return 'general_food', 'default'

# ---------- colour helpers ----------

RGB = tuple[int, int, int]


def rgb(hex_colour: str) -> RGB | None:
    if not isinstance(hex_colour, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', hex_colour):
        return None
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def hexed(c: RGB) -> str:
    return '#%02X%02X%02X' % c


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def ratio(fg: RGB, bg: RGB) -> float:
    return contrast(list(fg), list(bg))


def saturation(c: RGB) -> float:
    return colorsys.rgb_to_hsv(*(v / 255 for v in c))[1]


def adjust(c: RGB, sat: float = 1.0, light: float = 0.0) -> RGB:
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
    s = min(1.0, max(0.0, s * sat))
    l = min(0.97, max(0.03, l + light))
    return tuple(int(round(v * 255)) for v in colorsys.hls_to_rgb(h, l, s))


def lab(c: RGB) -> tuple[float, float, float]:
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in (x / 255 for x in c)]
    x = (0.4124564 * lin[0] + 0.3575761 * lin[1] + 0.1804375 * lin[2]) / 0.95047
    y = 0.2126729 * lin[0] + 0.7151522 * lin[1] + 0.0721750 * lin[2]
    z = (0.0193339 * lin[0] + 0.1191920 * lin[1] + 0.9503041 * lin[2]) / 1.08883
    f = [t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29 for t in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e(a: RGB, b: RGB) -> float:
    return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5


BLACK, WHITE = (17, 17, 17), (255, 255, 255)


def best_ink(background: RGB) -> RGB:
    return max((BLACK, WHITE), key=lambda c: (ratio(c, background), c == BLACK))

# ---------- decision 2: three layers ----------

@dataclass(frozen=True)
class Tone:
    light: RGB   # pale background tone
    dark: RGB    # deep background tone
    ink: RGB     # text on the pale tone
    accent: RGB  # default accent when the photo gives none


def _t(light, dark, ink, accent) -> Tone:
    return Tone(*(rgb(v) for v in (light, dark, ink, accent)))


# Layer 1. Directions from the design doc; final values are for the design owner to tune.
TONES = {
    'noodle_soup': _t('#EDC77E', '#1D1B1F', '#2A1D16', '#E3A72F'),     # amber broth / ink black, cream text, gold
    'fried_grill': _t('#F9CDB4', '#4A1A12', '#1A1410', '#E2412B'),     # warm peach / deep red-brown, near black, red-orange
    'rice_meal': _t('#F7F1E3', '#33351F', '#4A2E1A', '#E07A2E'),       # rice white / deep olive, brown, orange
    'fresh_light': _t('#DCEFD0', '#1F3D2A', '#1E4D2B', '#6FAE2F'),     # light green / deep green, green, lime
    'dessert_bakery': _t('#F9D5DE', '#4A1E2E', '#4A2C24', '#C2416B'),  # pale pink / plum, chocolate, berry
    'drink': _t('#E3CDB3', '#2E2119', '#3B2A20', '#8B5A3C'),           # latte beige / espresso, brown, coffee
}

# Layer 2. Mood shifts background and accent; type weight/spacing follow in a later PR.
MOOD_SHIFT = {  # (background saturation x, light background lightness +, dark background lightness +, accent saturation x)
    'warm': (1.0, 0.0, 0.0, 1.0),
    'minimal': (0.7, 0.02, 0.0, 0.8),
    'vivid': (1.3, -0.02, 0.0, 1.25),
    'premium': (0.75, -0.03, -0.03, 0.85),
}

# Template facts read from templates/v3/*.css (a test keeps them in step with the CSS):
# polarity of the background, polarity of the photo backdrop, and what accent-coloured text sits on
# Price templates draw header/footer/badge bands in --surface (dark by default) and show the period
# in the accent colour on the footer; collection templates inherit the ink colour for the period.
TEMPLATES = {  # template: (background, photo backdrop, band/panel/frame "surface", roles that accent text sits on,
    #             how strong the background colour is now: bold yellow/lime, pale cream, coloured deep green, neutral grey/black/white)
    'price_a': ('light', 'light', 'dark', ('surface',), 'bold'),
    'price_b': ('dark', 'light', 'dark', ('surface',), 'neutral'),
    'price_c': ('dark', 'light', 'dark', ('surface', 'bg'), 'neutral'),
    'price_d': ('light', 'light', 'dark', ('surface',), 'neutral'),
    'emotional_a': ('light', 'light', 'dark', (), 'neutral'), 'emotional_b': ('dark', 'light', 'light', (), 'coloured'),
    'emotional_c': ('light', 'light', 'dark', (), 'neutral'), 'emotional_d': ('dark', 'light', 'light', (), 'coloured'),
    'brand_a': ('dark', 'light', 'light', ('bg',), 'coloured'), 'brand_b': ('light', 'dark', 'dark', (), 'pale'),
    'brand_c': ('dark', 'light', 'light', (), 'coloured'), 'brand_d': ('light', 'light', 'dark', (), 'bold'),
    'visual_a': ('light', 'light', 'dark', (), 'neutral'), 'visual_b': ('light', 'light', 'light', (), 'neutral'),
    'visual_c': ('dark', 'dark', 'light', (), 'neutral'), 'visual_d': ('dark', 'light', 'light', (), 'neutral'),
}
# Templates that would otherwise get the same style as a sibling: price_b and price_c are both black today,
# so price_c takes a deep tint of the product colour and a product's four price drafts stay different.
LEVEL_OVERRIDE = {'price_c': 'coloured'}
TEXT_PAIRS = (('ink', 'bg'), ('ink-soft', 'bg'), ('surface-ink', 'surface'), ('accent-ink', 'accent'))
ACCENT_MIN_SHARE, ACCENT_MIN_SATURATION = 0.08, 0.25
HUE_MIN_VALUE = 0.35      # darker colours (black sauce, shadows) do not set the background hue
PHOTO_HUE_WEIGHT = 0.7    # background hue: 70 % photo, 30 % product kind
# Tint (lightness, saturation) = base + slope x the photo colour's own lightness/saturation, so a bright
# lemon gives a brighter, clearer tint than a brown latte of nearly the same hue. The template's current
# colour strength picks the row, so a product's four drafts keep different intensities (bold, pale, neutral).
TINT = {
    ('light', 'bold'): ((0.64, 0.10), (0.70, 0.25)), ('light', 'pale'): ((0.78, 0.14), (0.45, 0.45)),
    ('light', 'neutral'): ((0.87, 0.06), (0.50, 0.35)),
    ('dark', 'coloured'): ((0.13, 0.08), (0.35, 0.30)), ('dark', 'neutral'): ((0.11, 0.06), (0.30, 0.20)),
    ('ink', None): ((0.15, 0.0), (0.45, 0.0)),
}


def hue_source(palette) -> RGB | None:
    """The photo colour that sets the background hue: the largest clear, not-too-dark colour."""
    for c in accent_candidates(palette):
        if colorsys.rgb_to_hsv(*(v / 255 for v in c))[2] >= HUE_MIN_VALUE:
            return c
    return None


def _hue(c: RGB) -> float:
    return colorsys.rgb_to_hls(*(v / 255 for v in c))[0]


def mix_hue(photo: float, kind: float | None, photo_weight: float) -> float:
    """Weighted mean on the colour wheel, so red 350 deg and red 10 deg average to red 0 deg."""
    if kind is None:
        return photo
    x = photo_weight * math.cos(2 * math.pi * photo) + (1 - photo_weight) * math.cos(2 * math.pi * kind)
    y = photo_weight * math.sin(2 * math.pi * photo) + (1 - photo_weight) * math.sin(2 * math.pi * kind)
    return (math.atan2(y, x) / (2 * math.pi)) % 1.0


def _hls(h: float, l: float, s: float) -> RGB:
    return tuple(int(round(v * 255)) for v in colorsys.hls_to_rgb(h, l, s))


def tone_for(hue_colour: RGB, kind: str, template: tuple, photo_weight: float) -> Tone:
    """Tone with the hue of hue_colour (mixed with the kind hue) at this template's colour strength."""
    base = TONES.get(kind)
    h = mix_hue(_hue(hue_colour), _hue(base.light) if base else None, photo_weight)
    _, photo_l, photo_s = colorsys.rgb_to_hls(*(v / 255 for v in hue_colour))

    def tint(key):
        (l0, l1), (s0, s1) = TINT[key]
        return _hls(h, l0 + l1 * photo_l, s0 + s1 * photo_s)

    polarity, level = template[0], template[4]
    level = LEVEL_OVERRIDE.get(_template_id(template), level)
    light_level = level if polarity == 'light' else 'pale'
    dark_level = level if polarity == 'dark' else 'coloured'
    accent = base.accent if base else _hls(h, 0.45, 0.65)
    return Tone(light=tint(('light', light_level)), dark=tint(('dark', dark_level)), ink=tint(('ink', None)), accent=accent)


# How the hand-tuned table colours (pale / coloured) change for the other strengths: (saturation x, lightness +).
TABLE_LEVEL = {'bold': (1.4, -0.12), 'pale': (1.0, 0.0), 'neutral': (0.6, 0.04), 'coloured': (1.0, 0.0)}


def _template_id(template: tuple) -> str | None:
    return next((t for t, facts in TEMPLATES.items() if facts is template), None)


def table_tone(tone: Tone, template: tuple) -> Tone:
    polarity, level = template[0], LEVEL_OVERRIDE.get(_template_id(template), template[4])
    light = adjust(tone.light, *TABLE_LEVEL[level]) if polarity == 'light' else tone.light
    dark = adjust(tone.dark, TABLE_LEVEL[level][0], -0.02 if level == 'neutral' else 0.0) if polarity == 'dark' else tone.dark
    return Tone(light=light, dark=dark, ink=tone.ink, accent=tone.accent)


def accent_candidates(palette) -> list[RGB]:
    """Layer 3: photo colours covering >= 8 % with saturation >= 0.25, largest share first."""
    found = []
    for entry in palette or ():
        try:
            hex_colour, share = entry
        except (TypeError, ValueError):
            continue
        c = rgb(hex_colour)
        if (c and isinstance(share, (int, float)) and not isinstance(share, bool)
                and share >= ACCENT_MIN_SHARE and saturation(c) >= ACCENT_MIN_SATURATION):
            found.append((-float(share), hexed(c), c))
    return [c for *_, c in sorted(found)]


def _accent_ok(accent: RGB, colours: dict, text_on: tuple) -> bool:
    return (ratio(best_ink(accent), accent) >= CONTRAST_MINIMUM
            and all(ratio(accent, colours[role]) >= CONTRAST_MINIMUM for role in text_on))


def _readable_accent(accent: RGB, colours: dict, text_on: tuple) -> RGB:
    """The nearest tint or shade of the accent that carries readable text and is readable as text."""
    for step in range(0, 11):
        for target in (WHITE, BLACK):
            candidate = mix(accent, target, step / 10)
            if _accent_ok(candidate, colours, text_on):
                return candidate
    return BLACK if all(ratio(BLACK, colours[r]) >= CONTRAST_MINIMUM for r in text_on) else WHITE


def _colours(tone: Tone, mood: str, template: tuple) -> dict[str, RGB]:
    polarity, photo_polarity, surface_polarity = template[:3]
    bg_sat, light_shift, dark_shift, accent_sat = MOOD_SHIFT[mood]
    light = adjust(tone.light, bg_sat, light_shift)
    dark = adjust(tone.dark, bg_sat, dark_shift)
    if polarity == 'light':
        c = {'bg': light, 'ink': tone.ink, 'ink-soft': mix(tone.ink, light, 0.3), 'decor': mix(light, dark, 0.3)}
    else:
        c = {'bg': dark, 'ink': light, 'ink-soft': mix(light, dark, 0.3), 'decor': mix(dark, light, 0.25)}
    if surface_polarity == 'dark':
        c['surface'], c['surface-ink'] = dark, light
    else:  # a light panel on a light background stays a shade lighter than it, as the white frames do now
        c['surface'], c['surface-ink'] = (mix(light, WHITE, 0.7) if polarity == 'light' else light), tone.ink
    c['frame'] = c['surface']  # photo borders follow the band/panel colour in every template
    c['photo-bg'] = mix(light, dark, 0.07) if photo_polarity == 'light' else mix(dark, light, 0.12)
    c['accent'] = adjust(tone.accent, accent_sat)
    return c


@dataclass(frozen=True)
class StyleInput:
    template_id: str
    mood: str
    product_name: str
    palette: tuple[tuple[str, float], ...] = ()
    kind_hint: str | None = None
    kind_hint_margin: float | None = None
    user_kind: str | None = None


@dataclass(frozen=True)
class Style:
    version: str
    kind: str
    kind_source: str
    accent_source: str = 'none'      # 'photo' | 'kind' | 'none'
    background_source: str = 'none'  # 'photo' (hue from the photo) | 'kind' (table colours) | 'none'
    variables: dict[str, str] = field(default_factory=dict)

    def css(self) -> str:
        if not self.variables:
            return ''
        return '.ad{' + ';'.join(f'--{k}:{v}' for k, v in sorted(self.variables.items())) + '}'


def resolve_style(data: StyleInput) -> Style:
    kind, source = recognize_kind(data.product_name, data.kind_hint, data.kind_hint_margin, data.user_kind)
    template = TEMPLATES.get(data.template_id)
    photo = hue_source(data.palette)
    if template is None or data.mood not in MOODS or (kind not in TONES and photo is None):
        return Style(STYLE_VERSION, kind, source)
    text_on = template[3]
    if photo:
        tone, background_source = tone_for(photo, kind, template, PHOTO_HUE_WEIGHT), 'photo'
    else:  # no usable photo colour: the kind's table colours at this template's strength
        tone, background_source = table_tone(TONES[kind], template), 'kind'

    colours = _colours(tone, data.mood, template)
    accent_source = 'kind'
    # Layer 3: of the clear photo colours, the one that stands out most from the background.
    candidates = [adjust(c, MOOD_SHIFT[data.mood][3]) for c in accent_candidates(data.palette)]
    for candidate in sorted(candidates, key=lambda c: -delta_e(c, colours['bg'])):
        if _accent_ok(candidate, colours, text_on):
            colours['accent'], accent_source = candidate, 'photo'
            break
    # Final check: every text/background pair reaches 4.5:1. The accent moves to its nearest readable
    # tint/shade; other text falls back to the ink colour or to black/white.
    colours['accent'] = _readable_accent(colours['accent'], colours, text_on)
    colours['accent-ink'] = best_ink(colours['accent'])
    for fg, bg in TEXT_PAIRS:
        if ratio(colours[fg], colours[bg]) < CONTRAST_MINIMUM:
            colours[fg] = colours['ink'] if fg == 'ink-soft' and ratio(colours['ink'], colours[bg]) >= CONTRAST_MINIMUM \
                else best_ink(colours[bg])
    return Style(STYLE_VERSION, kind, source, accent_source, background_source,
                 {role: hexed(colours[role]) for role in ROLES})


def text_pairs(template_id: str) -> tuple[tuple[str, str], ...]:
    """Every (text, background) role pair that the template draws; used by tests and previews."""
    template = TEMPLATES.get(template_id)
    return TEXT_PAIRS + tuple(('accent', role) for role in (template[3] if template else ()))
