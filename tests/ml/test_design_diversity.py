"""Design-diversity scripts: synthetic images only, no model weights, no Chromium."""

import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load('ml_measure_design_diversity')
render_set = load('ml_render_diversity_set')


def test_delta_e_matches_known_values():
    assert measure.delta_e([255, 255, 255], [255, 255, 255]) == 0
    assert measure.delta_e([0, 0, 0], [255, 255, 255]) == pytest.approx(100, abs=0.01)
    assert measure.srgb_to_lab([255, 0, 0]) == pytest.approx([53.24, 80.09, 67.20], abs=0.05)


def test_background_is_the_largest_area():
    image = Image.new('RGB', (1080, 1350), (255, 216, 57))
    image.paste((17, 17, 17), (0, 0, 1080, 300))
    assert measure.background_colour(image) == [255, 216, 57]


def test_cosine_distance_is_scale_free():
    a = np.array([1.0, 0, 0])
    assert measure.cosine_distance(a, 5 * a) == pytest.approx(0)
    assert measure.cosine_distance(a, np.array([0, 1.0, 0])) == pytest.approx(1)


def ads():
    rows = []
    for product in ('cake', 'coffee', 'noodle'):
        for template in ('price_a', 'price_b', 'price_c', 'price_d'):
            rows.append({'product': product, 'strategy': 'price', 'template_id': template,
                         'file': f'{product}/{template}.png',
                         'diagnostics': {'contrast': 'normal', 'layout': 'problem' if (product, template) == ('cake', 'price_a') else 'normal',
                                         'font_size': 'caution' if template == 'price_d' else 'normal'}})
    return rows


def test_identical_ads_have_no_diversity():
    rows = ads()
    same = {r['file']: np.array([1.0, 2.0, 3.0]) for r in rows}
    colour = {r['file']: [10, 20, 30] for r in rows}
    between = measure.between_products(rows, same, colour)
    assert between['clip_distance']['max'] == 0 and between['background_delta_e']['max'] == 0
    assert between['per_template']['price_a']['products'] == 3
    assert between['by_kind_pair']['different_kind']['background_delta_e']['n'] == 4 * 3
    within = measure.within_product(rows, same, {r['file']: 0.0 for r in rows}, 0.2)
    assert within['clip_distance']['n'] == 3 * 6
    assert within['close_call_pairs'] == {'pairs': 18, 'close': 18, 'share': 1.0}


def test_kind_pairs_are_split():
    rows = ads()
    for r in rows:
        r['kind'] = 'drink' if r['product'] in ('cake', 'coffee') else 'noodle_soup'
    colour = {r['file']: [250, 220, 230] if r['product'] == 'cake' else [60, 40, 30] for r in rows}
    result = measure.between_products(rows, None, colour)['by_kind_pair']
    assert result['same_kind']['background_delta_e']['n'] == 4
    assert result['different_kind']['background_delta_e']['n'] == 8
    assert result['same_kind']['background_delta_e']['min'] > 50
    assert result['different_kind']['clip_distance'] is None


def test_score_gap_counts_only_close_pairs():
    rows = [r for r in ads() if r['product'] == 'cake']
    clip = {r['file']: np.eye(4)[i] for i, r in enumerate(rows)}
    scores = {r['file']: float(i) for i, r in enumerate(rows)}  # 0,1,2,3: every gap >= 1
    result = measure.within_product(rows, clip, scores, 0.2)
    assert result['close_call_pairs']['close'] == 0
    assert result['clip_distance']['mean'] == pytest.approx(1)


def test_quality_shares():
    result = measure.quality(ads())
    assert result['ads'] == 12
    assert result['no_problem_share'] == pytest.approx(11 / 12, abs=1e-4)
    assert result['all_normal_share'] == pytest.approx(8 / 12, abs=1e-4)
    assert result['per_rule']['font_size'] == {'caution': 0.25, 'normal': 0.75}


def test_kind_recognition_waits_for_design_style():
    assert measure.kind_recognition([{'kind': 'drink'}])['status'] == 'not_available'
    done = measure.kind_recognition([{'kind': 'drink', 'recognized_kind': 'drink', 'recognized_source': 'name'},
                                     {'kind': 'nonfood', 'recognized_kind': 'general_food', 'recognized_source': 'default'}])
    assert done['agreement'] == 0.5 and done['sources'] == {'default': 1, 'name': 1}


def test_training_distance_scale():
    rng = np.random.default_rng(0)
    reference = rng.normal(size=(1000, 8))
    result = measure.training_distance(reference[:3].copy(), reference)
    assert result['ads_nearest_distance']['max'] == pytest.approx(0, abs=1e-9)
    assert result['reference_nearest_distance_for_scale']['n'] == 500


def write_set(folder: Path):
    folder.mkdir()
    rows = []
    for product, colour in (('cake', (250, 220, 230)), ('coffee', (60, 40, 30))):
        (folder / product).mkdir()
        for template in ('price_a', 'price_b'):
            path = folder / product / f'{template}.png'
            Image.new('RGB', (1080, 1350), colour).save(path)
            rows.append({'product': product, 'kind': 'drink', 'strategy': 'price', 'template_id': template,
                         'file': f'{product}/{template}.png', 'png_sha256': sha256(path.read_bytes()).hexdigest(),
                         'diagnostics': {'contrast': 'normal'}})
    manifest = {'template_version': 'test', 'copy': 'mock-copy-v1 (fixed)', 'ads': rows,
                'products': [{'id': 'cake', 'kind': 'dessert_bakery'}, {'id': 'coffee', 'kind': 'drink'}]}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


def test_measure_without_model_is_deterministic(tmp_path):
    write_set(tmp_path / 'set')
    first = measure.measure(tmp_path / 'set', None, None)
    assert first == measure.measure(tmp_path / 'set', None, None)
    assert first['between_products']['clip_distance'].startswith('not_measured')
    assert first['between_products']['background_delta_e']['min'] > 50
    assert first['input']['kinds'] == {'dessert_bakery': 1, 'drink': 1}
    assert 'within_product' not in first


def test_measure_refuses_changed_png(tmp_path):
    write_set(tmp_path / 'set')
    Image.new('RGB', (1080, 1350), 'white').save(tmp_path / 'set/cake/price_a.png')
    with pytest.raises(ValueError, match='changed after rendering'):
        measure.measure(tmp_path / 'set', None, None)


def write_csv(folder: Path, body: str):
    for name in ('jajang.jpg', 'Latte Art.png'):
        Image.new('RGB', (40, 40), 'white').save(folder / name)
    path = folder / 'products.csv'
    path.write_text(body, encoding='utf-8')
    return path


def test_products_csv_is_read_with_stable_ids(tmp_path):
    path = write_csv(tmp_path, 'photo,product_name,price_text,kind\njajang.jpg,짜장면,"7,000원",noodle_soup\n'
                               'Latte Art.png,카페라테,"4,500원",drink\n')
    products = render_set.read_products(path)
    assert [p['id'] for p in products] == ['jajang', 'latte-art']
    assert products[0]['price_text'] == '7,000원' and products[1]['kind'] == 'drink'


@pytest.mark.parametrize('body, message', [
    ('photo,name,price_text,kind\n', 'header'),
    ('photo,product_name,price_text,kind\n', 'no products'),
    ('photo,product_name,price_text,kind\njajang.jpg,짜장면,"7,000원",noodles\n', 'kind must be'),
    ('photo,product_name,price_text,kind\nmissing.jpg,짜장면,"7,000원",noodle_soup\n', 'not found'),
    ('photo,product_name,price_text,kind\njajang.jpg,,"7,000원",noodle_soup\n', 'every column'),
])
def test_products_csv_errors(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        render_set.read_products(write_csv(tmp_path, body))
