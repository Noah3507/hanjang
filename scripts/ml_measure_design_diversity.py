"""Measure how different the generated ads are, for the design-diversity work.

Run from the repository root inside .venv-ml, on a folder written by
scripts/ml_render_diversity_set.py:
  .venv-ml/bin/python scripts/ml_measure_design_diversity.py \
      --input artifacts/diversity/baseline \
      --bundle artifacts/models/ranking/bt-logistic-v1 \
      --output artifacts/diversity/baseline-metrics.json
Optionally add --reference-dir data/features/<feature_version> to record how far the
ads are from the CreativeRanking training images (nearest-neighbour cosine distance).

What it reports (same input -> same JSON; no time stamps, no randomness):
  between_products  same template, different products: CLIP distance (1 - cosine) and
                    background colour difference (CIE76 delta E in Lab). Higher = more varied.
  within_product    the four drafts of one product and strategy: CLIP distance, and the share
                    of pairs whose preference scores differ by less than the bundle's
                    close_call_score_gap. Distance should not drop; the share should not rise.
  quality           share of ads per diagnostics status, from the render manifest.
  kind_recognition  agreement with the person-assigned kind, once ads record recognized_kind.
  training_distance optional, see above.
CLIP features are the preference model's own (extract_features); no new model.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DECIMALS = 4


# ---------- pure helpers (tested without the model) ----------

def summary(values) -> dict | None:
    values = np.asarray(list(values), dtype=np.float64)
    if values.size == 0:
        return None
    r = lambda x: round(float(x), DECIMALS)
    return {'n': int(values.size), 'mean': r(values.mean()), 'median': r(np.median(values)),
            'min': r(values.min()), 'max': r(values.max())}


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(1.0 - np.clip(a @ b, -1.0, 1.0))


def srgb_to_lab(rgb) -> np.ndarray:
    """sRGB 0-255 -> CIE Lab (D65)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ np.array([[0.4124564, 0.2126729, 0.0193339],
                        [0.3575761, 0.7151522, 0.1191920],
                        [0.1804375, 0.0721750, 0.9503041]])
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.array([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])]).T


def delta_e(rgb_a, rgb_b) -> float:
    return float(np.linalg.norm(srgb_to_lab(rgb_a) - srgb_to_lab(rgb_b)))


def background_colour(image: Image.Image) -> list[int]:
    """The colour covering the largest area: most common 16-level bin, averaged inside the bin."""
    small = np.asarray(image.convert('RGB').resize((108, 135), Image.Resampling.NEAREST)).reshape(-1, 3).astype(np.int64)
    bins = small // 16
    keys = bins[:, 0] * 256 + bins[:, 1] * 16 + bins[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    top = values[np.argmax(counts)]  # np.unique sorts, so ties resolve to the lowest key
    return [int(round(v)) for v in small[keys == top].mean(axis=0)]


def between_products(ads: list[dict], clip: dict | None, background: dict) -> dict:
    by_template = defaultdict(list)
    kind = {}
    for ad in ads:
        by_template[ad['template_id']].append(ad['file'])
        kind[ad['file']] = ad.get('kind')
    clip_all, colour_all, per_template = [], [], {}
    by_pair = {'same_kind': ([], []), 'different_kind': ([], [])}
    for template in sorted(by_template):
        files = sorted(by_template[template])
        c, e = [], []
        for a, b in combinations(files, 2):
            group = by_pair['same_kind' if kind[a] is not None and kind[a] == kind[b] else 'different_kind']
            e.append(delta_e(background[a], background[b]))
            group[1].append(e[-1])
            if clip:
                c.append(cosine_distance(clip[a], clip[b]))
                group[0].append(c[-1])
        clip_all += c
        colour_all += e
        per_template[template] = {'products': len(files), 'clip_distance': summary(c), 'background_delta_e': summary(e)}
    return {'clip_distance': summary(clip_all) if clip else 'not_measured (no --bundle)',
            'background_delta_e': summary(colour_all),
            'by_kind_pair': {name: {'clip_distance': summary(c) if clip else None, 'background_delta_e': summary(e)}
                             for name, (c, e) in by_pair.items()},
            'per_template': per_template}


def within_product(ads: list[dict], clip: dict, scores: dict | None, gap: float | None) -> dict:
    groups = defaultdict(list)
    for ad in ads:
        groups[(ad['product'], ad['strategy'])].append(ad['file'])
    distances, close, pairs = [], 0, 0
    per_strategy = defaultdict(list)
    for (_, strategy), files in sorted(groups.items()):
        for a, b in combinations(sorted(files), 2):
            d = cosine_distance(clip[a], clip[b])
            distances.append(d)
            per_strategy[strategy].append(d)
            if scores is not None:
                pairs += 1
                close += abs(scores[a] - scores[b]) < gap
    result = {'clip_distance': summary(distances),
              'per_strategy': {s: summary(v) for s, v in sorted(per_strategy.items())}}
    if scores is not None:
        result['close_call_score_gap'] = gap
        result['close_call_pairs'] = {'pairs': pairs, 'close': int(close),
                                      'share': round(close / pairs, DECIMALS) if pairs else None}
    return result


def quality(ads: list[dict]) -> dict:
    per_rule = defaultdict(Counter)
    worst = Counter()
    for ad in ads:
        statuses = ad.get('diagnostics') or {}
        for rule, status in statuses.items():
            per_rule[rule][status] += 1
        worst['problem' if 'problem' in statuses.values() else 'caution' if 'caution' in statuses.values() else 'normal'] += 1
    n = len(ads)
    share = lambda count: round(count / n, DECIMALS) if n else None
    return {'ads': n,
            'no_problem_share': share(n - worst['problem']),
            'all_normal_share': share(worst['normal']),
            'per_rule': {rule: {status: share(c) for status, c in sorted(counter.items())}
                         for rule, counter in sorted(per_rule.items())}}


def kind_recognition(products: list[dict]) -> dict:
    checked = [p for p in products if p.get('recognized_kind')]
    if not checked:
        return {'status': 'not_available', 'reason': 'products carry no recognized_kind yet (design_style.py)'}
    agree = sum(p['recognized_kind'] == p['kind'] for p in checked)
    return {'status': 'measured', 'products': len(checked), 'agreement': round(agree / len(checked), DECIMALS),
            'sources': dict(sorted(Counter(p.get('recognized_source', 'unknown') for p in checked).items()))}


def nearest_distance(queries: np.ndarray, reference: np.ndarray, batch: int = 4096) -> np.ndarray:
    q = queries / np.linalg.norm(queries, axis=1, keepdims=True)
    best = np.full(len(q), -1.0)
    for start in range(0, len(reference), batch):
        r = reference[start:start + batch]
        r = r / np.linalg.norm(r, axis=1, keepdims=True)
        best = np.maximum(best, (q @ r.T).max(axis=1))
    return 1.0 - best


def training_distance(ad_clip: np.ndarray, reference: np.ndarray) -> dict:
    """Ads vs train images, next to train-vs-train (500 fixed held-out rows) for scale."""
    held = np.zeros(len(reference), dtype=bool)
    held[np.unique(np.linspace(0, len(reference) - 1, min(500, len(reference) // 2)).astype(int))] = True
    return {'reference_images': int(len(reference)),
            'ads_nearest_distance': summary(nearest_distance(ad_clip, reference)),
            'reference_nearest_distance_for_scale': summary(nearest_distance(reference[held], reference[~held]))}


# ---------- model side ----------

def load_reference(folder: Path) -> np.ndarray:
    import pandas as pd
    clip = np.load(folder / 'creativeranking_clip.npy')
    index = pd.read_parquet(folder / 'creativeranking_index.parquet')
    if len(index) != len(clip):
        raise ValueError('reference index and embeddings differ in length')
    return clip[(index['split'] == 'train').to_numpy()] if 'split' in index.columns else clip


def measure(folder: Path, bundle: Path | None, reference_dir: Path | None) -> dict:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    ads = sorted(manifest['ads'], key=lambda a: a['file'])
    for ad in ads:
        if sha256((folder / ad['file']).read_bytes()).hexdigest() != ad['png_sha256']:
            raise ValueError(f'{ad["file"]} changed after rendering')
    background = {}
    for ad in ads:
        with Image.open(folder / ad['file']) as image:
            background[ad['file']] = background_colour(image)
    clip, scores, gap, model_version = {}, None, None, None
    if bundle is not None:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from ml.inference.api import extract_features, load_model, _score
        model = load_model(bundle)
        width = int(model.clip['embedding_dim'])
        scores, gap, model_version = {}, model.close_call_score_gap, model.model_version
        for ad in ads:
            features = extract_features(folder / ad['file'], model)
            clip[ad['file']] = np.array(features[:width])
            scores[ad['file']] = _score(features, model)
    result = {
        'input': {'folder_name': folder.name, 'manifest_sha256': sha256((folder / 'manifest.json').read_bytes()).hexdigest(),
                  'template_version': manifest.get('template_version'), 'copy': manifest.get('copy'),
                  'products': len(manifest['products']), 'ads': len(ads),
                  'kinds': dict(sorted(Counter(p['kind'] for p in manifest['products']).items()))},
        'model_version': model_version,
        'background_colours': {f: background[f] for f in sorted(background)},
        'quality': quality(ads),
        'kind_recognition': kind_recognition(manifest['products']),
    }
    result['between_products'] = between_products(ads, clip or None, background)
    if clip:
        result['within_product'] = within_product(ads, clip, scores, gap)
        if reference_dir is not None:
            result['training_distance'] = training_distance(np.stack([clip[a['file']] for a in ads]),
                                                            load_reference(reference_dir))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True, help='folder written by ml_render_diversity_set.py')
    parser.add_argument('--bundle', type=Path, help='preference model bundle folder (for CLIP distance and scores)')
    parser.add_argument('--reference-dir', type=Path, help='data/features/<feature_version> for training distance')
    parser.add_argument('--output', type=Path, required=True, help='result JSON; must not exist yet')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output file already exists; choose a new name so earlier results are kept')
    if args.reference_dir and not args.bundle:
        parser.error('--reference-dir needs --bundle')
    result = measure(args.input, args.bundle, args.reference_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    brief = {'ads': result['input']['ads'], 'no_problem_share': result['quality']['no_problem_share']}
    for part in ('between_products', 'within_product'):
        value = result.get(part, {}).get('clip_distance')
        if isinstance(value, dict):
            brief[part + '_clip_mean'] = value['mean']
    print(json.dumps(brief, ensure_ascii=False))


if __name__ == '__main__':
    main()
