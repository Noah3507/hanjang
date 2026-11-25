"""Render every v3 template for a fixed set of product photos, for the design-diversity measurement.

Run from the repository root with the service environment (.venv), which has the
background-removal model, Node and Chromium:
  .venv/bin/python scripts/ml_render_diversity_set.py \
      --products artifacts/diversity-photos/products.csv \
      --output artifacts/diversity/baseline

products.csv (UTF-8, header row; photo paths are relative to the CSV file):
  photo,product_name,price_text,kind
  jajang.jpg,짜장면,"7,000원",noodle_soup

kind is the group a person assigns (noodle_soup, fried_grill, rice_meal, fresh_light,
dessert_bakery, drink, nonfood, general_food); it is recorded, not used to render.

Copy is always the fixed Mock copy, so only the design differs between runs.

With --style-mood warm|minimal|vivid|premium, each ad also gets the per-product style
from backend/app/services/design_style.py (kind from the product name, accent from the
photo palette), injected as CSS variables the same way the service will. Without it the
templates render exactly as in the service today (the baseline):
  .venv/bin/python scripts/ml_render_diversity_set.py --products ... \
      --output artifacts/diversity/style-v1-warm --style-mood warm
No API calls, no uploads. Photos and PNGs stay under artifacts/ (ignored by git).

With --photo-mode original, the background is not removed: the whole photo (EXIF-rotated, longer side
at most the service's photo size) goes into the templates, which show it as a rounded card. The palette
for the style then comes from the whole photo.

Writes <output>/<product id>/<template id>.png and <output>/manifest.json, which
scripts/ml_measure_design_diversity.py reads. The output folder must not exist yet.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('noodle_soup', 'fried_grill', 'rice_meal', 'fresh_light', 'dessert_bakery', 'drink', 'nonfood', 'general_food')
STRATEGIES = ('emotional', 'price', 'visual', 'brand')
COLUMNS = ['photo', 'product_name', 'price_text', 'kind']
RENDER_SOURCES = ('backend/app/services/template_v3.py', 'backend/app/services/template_v3_claims.py',
                  'backend/app/services/design_style.py', 'scripts/service_render_v3_worker.mjs')


def read_products(path: Path) -> list[dict]:
    """Rows of the CSV with a stable id per photo; raises ValueError on any problem."""
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or [f.strip() for f in reader.fieldnames] != COLUMNS:
            raise ValueError(f'products.csv header must be exactly: {",".join(COLUMNS)}')
        rows = [{k.strip(): (v or '').strip() for k, v in row.items()} for row in reader]
    if not rows:
        raise ValueError('products.csv has no products')
    products, seen = [], set()
    for number, row in enumerate(rows, start=2):
        if not all(row[c] for c in COLUMNS):
            raise ValueError(f'line {number}: every column needs a value')
        if row['kind'] not in KINDS:
            raise ValueError(f'line {number}: kind must be one of {", ".join(KINDS)}')
        photo = (path.parent / row['photo']).resolve()
        if not photo.is_file():
            raise ValueError(f'line {number}: photo not found: {row["photo"]}')
        product_id = re.sub(r'[^A-Za-z0-9_-]+', '-', photo.stem).strip('-').lower() or f'product-{number}'
        if product_id in seen:
            raise ValueError(f'line {number}: two photos share the id {product_id}; rename one file')
        seen.add(product_id)
        products.append({'id': product_id, 'photo': photo, 'product_name': row['product_name'],
                         'price_text': row['price_text'], 'kind': row['kind']})
    return products


def mock_copy() -> dict:
    """strategy -> {headline, body, cta} from the service's own Mock provider."""
    from app.services.copy_provider import MockCopyProvider
    variants = json.loads(MockCopyProvider().generate(None).text)['variants']
    return {v['strategy']: v['copy'] for v in variants}


def source_hashes() -> dict:
    files = [ROOT / p for p in RENDER_SOURCES] + sorted((ROOT / 'templates/v3').glob('*'))
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}


def rule_statuses(diagnostics) -> dict:
    data = diagnostics.model_dump(mode='json') if hasattr(diagnostics, 'model_dump') else diagnostics
    return {rule['rule_id']: rule['status'] for rule in data['rules']}


def product_style(product: dict, png: bytes, mood: str) -> dict:
    """Styles for all 16 templates, scoped per template so one CSS string serves a whole render call."""
    from app.services.analysis_palette import extract_palette
    from app.services.design_style import STYLE_VERSION, StyleInput, resolve_style
    from app.services.template_v3 import REGISTRY
    palette = tuple((c.hex, c.proportion) for c in extract_palette(png).colors)
    styles = {t: resolve_style(StyleInput(t, mood, product['product_name'], palette)) for t in sorted(REGISTRY)}
    first = next(iter(styles.values()))
    css = ''.join(style.css().replace('.ad{', f'.ad.{t}{{', 1) for t, style in styles.items())
    return {'version': STYLE_VERSION, 'mood': mood, 'kind': first.kind, 'kind_source': first.kind_source,
            'palette': [[h, round(share, 4)] for h, share in palette], 'css': css,
            'templates': {t: {'accent_source': s.accent_source, 'variables': s.variables} for t, s in styles.items()}}


@contextmanager
def extra_template_css(css: str):
    """Append CSS after quality.css while the renderer reads the template files (preview only)."""
    original = Path.read_text

    def read_text(self, *args, **kwargs):
        text = original(self, *args, **kwargs)
        return text + css if css and self.name == 'quality.css' and self.parent.name == 'v3' else text

    with mock.patch.object(Path, 'read_text', read_text):
        yield


def whole_photo(max_side: int):
    """Stand-in for background removal that keeps the whole photo, as an opaque PNG."""
    from io import BytesIO
    from PIL import Image, ImageOps
    from app.services.photo_processor import ProcessedPhoto

    def keep(raw: bytes):
        with Image.open(BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert('RGB')
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, 'PNG')
        return ProcessedPhoto(buffer.getvalue(), None, image.width, image.height, [])
    return keep


def render_set(products: list[dict], output: Path, store_name: str, remove_background, render,
               mood: str | None = None, photo_mode: str = 'cutout') -> dict:
    from app.services.template_v3 import TemplateInput, VERSION
    from app.services.render_execution import RenderFailure
    copies = mock_copy()
    hashes = source_hashes()
    output.mkdir(parents=True)
    manifest = {'purpose': 'design-diversity measurement set', 'copy': 'mock-copy-v1 (fixed)',
                'template_version': VERSION, 'store_name': store_name, 'renderer_source_hashes': hashes,
                'style': {'mood': mood} if mood else 'none (templates as in the service)',
                'photo_mode': photo_mode,
                'products': [], 'ads': []}
    for product in products:
        raw = product['photo'].read_bytes()
        entry = {k: product[k] for k in ('id', 'product_name', 'price_text', 'kind')}
        entry['photo_sha256'] = sha256(raw).hexdigest()
        processed = remove_background(raw)
        entry['photo_warnings'] = list(processed.warnings)
        if processed.png is None:
            entry['status'] = 'photo_failed'
            manifest['products'].append(entry)
            print(f'{product["id"]}: background removal failed {processed.warnings}', file=sys.stderr)
            continue
        style = product_style(product, processed.png, mood) if mood else None
        if style:
            entry.update(recognized_kind=style['kind'], recognized_source=style['kind_source'],
                         style_version=style['version'], palette=style['palette'])
        folder = output / product['id']
        folder.mkdir()
        failures = []
        for strategy in STRATEGIES:
            text = copies[strategy]
            data = TemplateInput(store_name, product['product_name'], product['price_text'],
                                 text['headline'], text['body'], text['cta'])
            ids = [f'{strategy}_{c}' for c in 'abcd']
            try:
                with extra_template_css(style['css'] if style else ''):
                    rows = render(data, processed.png, ids)
            except RenderFailure as error:
                failures.append({'strategy': strategy, 'error': error.code})
                print(f'{product["id"]} {strategy}: {error.code}', file=sys.stderr)
                continue
            for row in rows:
                name = f'{row["template_id"]}.png'
                (folder / name).write_bytes(row['png'])
                manifest['ads'].append({
                    'product': product['id'], 'kind': product['kind'], 'template_id': row['template_id'],
                    'strategy': row['strategy'], 'file': f'{product["id"]}/{name}',
                    'png_sha256': sha256(row['png']).hexdigest(),
                    'diagnostics': rule_statuses(row['diagnostics']),
                    'fit_steps': row.get('measurement', {}).get('fit_steps'),
                    'style': style['templates'][row['template_id']] if style else None})
        entry['status'] = 'rendered' if not failures else 'partial'
        entry['render_failures'] = failures
        manifest['products'].append(entry)
        print(f'{product["id"]}: {16 - 4 * len(failures)} ads', file=sys.stderr)
    manifest['renderer_sources_unchanged_during_render'] = hashes == source_hashes()
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--products', type=Path, required=True, help='products.csv')
    parser.add_argument('--output', type=Path, required=True, help='new folder, e.g. artifacts/diversity/baseline')
    parser.add_argument('--store-name', default='한장 테스트 가게')
    parser.add_argument('--photo-mode', choices=['cutout', 'original'], default='cutout',
                        help='cutout: remove the background as the service does; original: keep the whole photo')
    parser.add_argument('--style-mood', choices=['warm', 'minimal', 'vivid', 'premium'],
                        help='apply design_style.py with this mood (omit for the baseline)')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output folder already exists; choose a new name so earlier results are kept')
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.config import Settings
    from app.services.photo_execution import PhotoExecution
    from app.services.template_v3 import render_templates
    settings = Settings()
    if not settings.photo_model_path.is_file():
        parser.error(f'background-removal model not found: {settings.photo_model_path}')
    products = read_products(args.products)
    remove = (whole_photo(settings.photo_max_side) if args.photo_mode == 'original'
              else PhotoExecution(settings.photo_model_path, settings.photo_timeout_seconds, settings.photo_max_side))
    manifest = render_set(products, args.output, args.store_name, remove,
                          lambda data, png, ids: render_templates(data, png, ids, timeout=180), args.style_mood,
                          args.photo_mode)
    print(json.dumps({'products': len(manifest['products']), 'ads': len(manifest['ads']),
                      'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
