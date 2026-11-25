"""Measure the grey haze that background removal leaves around a product, and preview cleanups.

Run from the repository root with the service environment (.venv):
  .venv/bin/python scripts/ml_cutout_haze.py \
      --products artifacts/diversity-photos/products.csv --output artifacts/cutout-haze

For every photo it runs the service's own background removal, then writes
  <output>/sheet.png    each product on a light and a dark poster colour: as now, and three cleanups
  <output>/haze.json    haze share per product and per cleanup
Nothing here changes the service. Bowls, plates and separate pieces (gimbap slices) count as product:
the cleanups only drop faint pixels and pixels far from any solid part of the cut-out.

  raw       the cut-out as the service makes it today
  faint     pixels under alpha FAINT_ALPHA become fully transparent
  near      pixels farther than NEAR_FRACTION of the cut-out size from a solid part become transparent
  both      faint + near
  solid     keep what the model half-erased but is attached to the product (a plate, a bowl rim) and make
            it fully opaque again with its own original pixels; drop the rest of the faint pixels
"""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOLID_ALPHA = 128        # pixels at or above this are surely product
FAINT_ALPHA = 64         # "faint" cleanup cut-off
NEAR_FRACTION = 0.03     # "near" cleanup keeps pixels within 3 % of the cut-out's longer side of a solid part
MIN_PIECE = 0.01         # solid pieces smaller than 1 % of all solid area are ignored as noise
SOLID_FROM = 48         # "solid" cleanup: attached pixels at or above this become fully opaque
POSTERS = ((246, 205, 180), (58, 26, 18))  # a light and a dark poster colour from the style table


def solid_core(alpha: np.ndarray) -> np.ndarray:
    import cv2
    solid = (alpha >= SOLID_ALPHA).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    if count <= 1:
        return solid.astype(bool)
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i, area in enumerate(areas) if area >= MIN_PIECE * areas.sum()]
    return np.isin(labels, keep)


def near_zone(core: np.ndarray) -> np.ndarray:
    import cv2
    ys, xs = np.nonzero(core)
    if len(xs) == 0:
        return core
    size = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    radius = max(2, int(round(size * NEAR_FRACTION)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    return cv2.dilate(core.astype(np.uint8), kernel).astype(bool)


def attached_solid(alpha: np.ndarray) -> np.ndarray:
    """Regions at or above SOLID_FROM that touch a solid piece become opaque; everything else transparent.
    The edge keeps a one-pixel soft step so the outline is not jagged."""
    import cv2
    core = solid_core(alpha)
    region = (alpha >= SOLID_FROM).astype(np.uint8)
    count, labels = cv2.connectedComponents(region, connectivity=8)
    touching = np.unique(labels[core & (labels > 0)])
    kept = np.isin(labels, touching[touching > 0]).astype(np.uint8) * 255
    return cv2.GaussianBlur(kept, (3, 3), 0)


def cleanups(alpha: np.ndarray) -> dict[str, np.ndarray]:
    zone = near_zone(solid_core(alpha))
    faint = np.where(alpha < FAINT_ALPHA, 0, alpha)
    return {'raw': alpha, 'faint': faint, 'near': np.where(zone, alpha, 0), 'both': np.where(zone, faint, 0),
            'solid': attached_solid(alpha)}


def haze_share(alpha: np.ndarray) -> float:
    """Share of all alpha mass that is faint (< SOLID_ALPHA) and not right at a solid edge."""
    import cv2
    core = solid_core(alpha)
    edge = cv2.dilate(core.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    total = float(alpha.sum())
    stray = alpha[(alpha > 0) & (alpha < SOLID_ALPHA) & ~edge].sum()
    return round(float(stray) / total, 4) if total else 0.0


def on_poster(rgba: Image.Image, alpha: np.ndarray, colour, size=220) -> Image.Image:
    image = rgba.copy()
    image.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    image.thumbnail((size - 20, size - 20))
    poster = Image.new('RGB', (size, size), colour)
    poster.paste(image, ((size - image.width) // 2, (size - image.height) // 2), image)
    return poster


def run(products: list[dict], remove_background, output: Path) -> dict:
    output.mkdir(parents=True)
    names = ['raw', 'faint', 'near', 'both', 'solid']
    cell, label = 220, 30
    font_path = ROOT / 'templates/fonts/NotoSansKR-Bold.otf'
    font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    sheet = Image.new('RGB', (130 + len(names) * 2 * cell, label + len(products) * cell), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        draw.text((130 + i * 2 * cell + 10, 6), f'{name} (밝은 / 어두운 배경)', fill='black', font=font)
    report = {'solid_alpha': SOLID_ALPHA, 'faint_alpha': FAINT_ALPHA, 'near_fraction': NEAR_FRACTION,
              'solid_from': SOLID_FROM, 'products': []}
    for row, product in enumerate(products):
        processed = remove_background(product['photo'].read_bytes())
        y = label + row * cell
        draw.text((8, y + cell // 2 - 10), product['product_name'], fill='black', font=font)
        entry = {'id': product['id'], 'product_name': product['product_name']}
        if processed.png is None:
            entry['status'] = 'photo_failed'
            report['products'].append(entry)
            continue
        with Image.open(BytesIO(processed.png)) as opened:
            rgba = opened.convert('RGBA')
        alpha = np.asarray(rgba.getchannel('A'))
        variants = cleanups(alpha)
        entry['haze'] = {name: haze_share(a) for name, a in variants.items()}
        entry['removed_alpha_share'] = {name: round(1 - float(a.sum()) / float(alpha.sum()), 4)
                                        for name, a in variants.items()}  # negative = made more opaque
        report['products'].append(entry)
        for i, name in enumerate(names):
            for j, colour in enumerate(POSTERS):
                sheet.paste(on_poster(rgba, variants[name], colour, cell), (130 + (2 * i + j) * cell, y))
        print(f"{product['id']}: haze {entry['haze']['raw']} -> both {entry['haze']['both']}", file=sys.stderr)
    sheet.save(output / 'sheet.png')
    (output / 'haze.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--products', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output folder already exists; choose a new name')
    sys.path.insert(0, str(ROOT / 'backend'))
    sys.path.insert(0, str(ROOT / 'scripts'))
    from ml_render_diversity_set import read_products
    from app.config import Settings
    from app.services.photo_execution import PhotoExecution
    settings = Settings()
    remove = PhotoExecution(settings.photo_model_path, settings.photo_timeout_seconds, settings.photo_max_side)
    report = run(read_products(args.products), remove, args.output)
    print(json.dumps({p['id']: p.get('haze', {}).get('raw') for p in report['products']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
