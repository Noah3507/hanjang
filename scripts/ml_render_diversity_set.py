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
No API calls, no uploads. Photos and PNGs stay under artifacts/ (ignored by git).

Writes <output>/<product id>/<template id>.png and <output>/manifest.json, which
scripts/ml_measure_design_diversity.py reads. The output folder must not exist yet.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('noodle_soup', 'fried_grill', 'rice_meal', 'fresh_light', 'dessert_bakery', 'drink', 'nonfood', 'general_food')
STRATEGIES = ('emotional', 'price', 'visual', 'brand')
COLUMNS = ['photo', 'product_name', 'price_text', 'kind']
RENDER_SOURCES = ('backend/app/services/template_v3.py', 'backend/app/services/template_v3_claims.py',
                  'scripts/service_render_v3_worker.mjs')


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


def render_set(products: list[dict], output: Path, store_name: str, remove_background, render) -> dict:
    from app.services.template_v3 import TemplateInput, VERSION
    from app.services.render_execution import RenderFailure
    copies = mock_copy()
    hashes = source_hashes()
    output.mkdir(parents=True)
    manifest = {'purpose': 'design-diversity measurement set', 'copy': 'mock-copy-v1 (fixed)',
                'template_version': VERSION, 'store_name': store_name, 'renderer_source_hashes': hashes,
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
        folder = output / product['id']
        folder.mkdir()
        failures = []
        for strategy in STRATEGIES:
            text = copies[strategy]
            data = TemplateInput(store_name, product['product_name'], product['price_text'],
                                 text['headline'], text['body'], text['cta'])
            ids = [f'{strategy}_{c}' for c in 'abcd']
            try:
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
                    'fit_steps': row.get('measurement', {}).get('fit_steps')})
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
    remove = PhotoExecution(settings.photo_model_path, settings.photo_timeout_seconds, settings.photo_max_side)
    manifest = render_set(products, args.output, args.store_name, remove,
                          lambda data, png, ids: render_templates(data, png, ids, timeout=180))
    print(json.dumps({'products': len(manifest['products']), 'ads': len(manifest['ads']),
                      'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
