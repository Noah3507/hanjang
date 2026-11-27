"""Measure how much text each v3 template slot holds, and write templates/v3/limits.json.

The copy prompt and checks (A) need to know how long a headline, body or CTA may be. Instead of
guessing, this renders every template in Chromium with longer and longer Korean text and records:

  soft  the longest text that fits at the template's own font size (nothing shrinks)
  hard  the longest text that still fits after the renderer shrinks it, as long as the final size
        stays at or above the readability threshold of that role (diagnostics_engine.ROLE_THRESHOLDS,
        or the starting size if a template starts below it)

Lengths count every character the reader sees, spaces included, after the store name, product name
and price have been filled in. The text is ordinary Korean words (see SAMPLE), so wrapping behaves
like real copy. Very short words or no spaces can fit a few characters fewer.

Each strategy's four templates share one copy, so per-strategy limits are the minimum of its four.
A field is measured with every other field present, which is the tightest layout; when the body or
CTA is empty the templates give that room to the photo, not to the other fields.

Run from the repository root in the service .venv (Node and Chromium needed, about 5 minutes):
  .venv/bin/python scripts/ml_measure_template_limits.py
  .venv/bin/python scripts/ml_measure_template_limits.py --check   # compare with the saved file only
No API calls. Writes templates/v3/limits.json (or nothing with --check).
"""
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
OUT = ROOT / 'templates' / 'v3' / 'limits.json'
SAMPLE = ('오늘은 따뜻한 국물에 바삭한 튀김을 곁들인 든든한 한 끼를 천천히 즐겨 보세요 '
          '퇴근길에 들르기 좋은 가게에서 갓 만든 메뉴를 바로 받아 가세요 ')
BASE = {'store_name': '골목반점', 'product_name': '짜장면', 'price_text': '7,000원',
        'headline': '오늘의 한 그릇', 'body': '갓 볶은 춘장으로 만들었어요', 'cta': '지금 주문하세요'}
COPY_FIELDS = ('headline', 'body', 'cta')
FACT_FIELDS = ('store_name', 'product_name')
STEP = {'headline': 2, 'body': 4, 'cta': 1, 'store_name': 1, 'product_name': 1}
CEILING = {'headline': 80, 'body': 160, 'cta': 30, 'store_name': 40, 'product_name': 40}


def text_of(n: int) -> str:
    """n visible characters of ordinary Korean copy, never ending on a space."""
    source = SAMPLE * (n // len(SAMPLE) + 2)
    out = source[:n]
    return out[:-1] + source[n] if out.endswith(' ') else out


def photo() -> bytes:
    from PIL import Image, ImageDraw
    buffer = BytesIO()
    image = Image.new('RGBA', (600, 450))
    ImageDraw.Draw(image).ellipse((20, 20, 580, 430), fill='white')
    image.save(buffer, 'PNG')
    return buffer.getvalue()


def source_hash() -> str:
    """Everything that decides where text goes. limits.json must be re-measured when this changes."""
    files = sorted((ROOT / 'templates/v3').glob('*.html')) + [ROOT / 'templates/v3' / n for n in ('price.css', 'collection.css', 'quality.css')]
    digest = sha256()
    for path in files:
        digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


class Measurer:
    def __init__(self):
        from app.services.diagnostics_engine import BODY_TEMPLATE_EXCEPTIONS, FIELD_ROLES, ROLE_THRESHOLDS
        from app.services.template_v3 import REGISTRY, TemplateInput, render_templates
        self.render, self.Input = render_templates, TemplateInput
        self.ids = sorted(t for t, v in REGISTRY.items() if v['implemented'])
        self.roles, self.thresholds, self.exceptions = FIELD_ROLES, ROLE_THRESHOLDS, BODY_TEMPLATE_EXCEPTIONS
        self.png = photo()

    def floor(self, template_id: str, field: str, initial: float) -> float:
        threshold = self.thresholds[self.roles[field]]
        if field == 'body' and template_id in self.exceptions:
            threshold = self.exceptions[template_id]
        return min(threshold, initial)

    def outcome(self, field: str, n: int, ids: list[str]) -> dict[str, str]:
        """template id -> 'soft' (fits unshrunk), 'hard' (shrunk, still readable) or 'no'."""
        from app.services.render_execution import RenderFailure
        data = self.Input(**{**BASE, field: text_of(n)})
        try:
            rows = self.render(data, self.png, ids, timeout=240)
        except RenderFailure:
            if len(ids) == 1:
                return {ids[0]: 'no'}
            result = {}
            for t in ids:
                result.update(self.outcome(field, n, [t]))
            return result
        result = {}
        for row in rows:
            item = next(t for t in row['measurement']['text'] if t['field'] == field)
            if row['measurement'].get('text_collisions'):
                result[row['template_id']] = 'no'
            elif item['font_size_px'] >= item['initial_font_size_px'] - 0.01:
                result[row['template_id']] = 'soft'
            elif item['font_size_px'] >= self.floor(row['template_id'], field, item['initial_font_size_px']) - 0.01:
                result[row['template_id']] = 'hard'
            else:
                result[row['template_id']] = 'no'
        return result

    def field(self, field: str) -> dict[str, dict[str, int]]:
        """Sweep lengths upward; a template stops being tested once it no longer fits."""
        limits = {t: {'soft': 0, 'hard': 0} for t in self.ids}
        open_ids = list(self.ids)
        n = STEP[field]
        while open_ids and n <= CEILING[field]:
            for t, state in self.outcome(field, n, open_ids).items():
                if state == 'soft':
                    limits[t]['soft'] = limits[t]['hard'] = n
                elif state == 'hard':
                    limits[t]['hard'] = n
                else:
                    open_ids.remove(t)
            print(f'{field} {n}: {len(open_ids)} templates still fit', file=sys.stderr)
            n += STEP[field]
        for t in open_ids:  # fits even the longest tried; record the ceiling and say so
            limits[t]['at_ceiling'] = True
        return limits


def build(measured: dict) -> dict:
    from app.services.template_v3 import REGISTRY, VERSION
    strategies = sorted({REGISTRY[t]['strategy'] for t in next(iter(measured.values()))})
    per_strategy = {}
    for s in strategies:
        ids = [t for t in sorted(REGISTRY) if REGISTRY[t]['strategy'] == s]
        per_strategy[s] = {f: {k: min(measured[f][t][k] for t in ids) for k in ('soft', 'hard')} for f in COPY_FIELDS}
        per_strategy[s]['tightest_template'] = {f: min(ids, key=lambda t: (measured[f][t]['soft'], t)) for f in COPY_FIELDS}
    return {
        'schema': 'hanjang-template-limits-1',
        'template_version': VERSION,
        'source_sha256': source_hash(),
        'counting': 'visible characters including spaces, after store_name/product_name/price_text are filled in',
        'soft': 'fits at the template font size (nothing shrinks)',
        'hard': 'fits after shrinking, final size >= readability threshold of the role (diagnostics_engine.ROLE_THRESHOLDS)',
        'fixed_slots': {
            'fields': ['store_name', 'product_name', 'price_text'],
            'rule': 'All 16 templates show these three in their own slots. Copy (headline, body, cta) does not need to '
                    'repeat them; repeating the price or "store의 product" doubles what the slot already shows.',
        },
        'empty_allowed': {'headline': False, 'body': True, 'cta': True,
                          'note': 'An empty body or CTA gives its room to the photo (templates/v3/quality.css, Fill).'},
        'strategies': per_strategy,
        'templates': {t: {f: measured[f][t] for f in measured} for t in sorted(next(iter(measured.values())))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--check', action='store_true', help='only report whether limits.json matches the templates')
    args = parser.parse_args()
    if args.check:
        saved = json.loads(OUT.read_text(encoding='utf-8'))
        same = saved['source_sha256'] == source_hash()
        print('limits.json matches the templates' if same else 'templates changed: re-run without --check')
        sys.exit(0 if same else 1)
    m = Measurer()
    measured = {f: m.field(f) for f in COPY_FIELDS + FACT_FIELDS}
    data = build(measured)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(data['strategies'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
