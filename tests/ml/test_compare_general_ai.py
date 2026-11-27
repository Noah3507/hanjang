"""General-AI comparison script: synthetic images only, no server, no model weights.

Runs in the service .venv (OpenCV and scikit-image come from backend/requirements.txt):
  .venv/bin/python -m pytest tests/ml/test_compare_general_ai.py
The OCR test runs only where Tesseract with Korean data is installed.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

pytest.importorskip('cv2')
pytest.importorskip('skimage')

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('compare', ROOT / 'scripts' / 'ml_compare_general_ai.py')
compare = importlib.util.module_from_spec(spec)
sys.modules['compare'] = compare  # dataclasses look their module up by name
spec.loader.exec_module(compare)
Word = compare.Word
CASE = {'case_id': 'c1', 'store_name': '골목카페', 'product_name': '아메리카노', 'price_text': '4,500원',
        'product_features': '직접 내린 수제 커피'}


def words(*texts):
    return [Word(t, (0, 0, 10, 10)) for t in texts]


def textured(size=(800, 600), seed=1):
    """A photo-like image with many corners, so keypoints exist."""
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (size[1] // 8, size[0] // 8, 3), dtype=np.uint8)
    return Image.fromarray(small).resize(size, Image.NEAREST).filter(ImageFilter.GaussianBlur(1))


def test_claim_list_is_the_copy_validators():
    pattern = compare.claim_pattern()
    assert pattern.search('오늘만 할인') and pattern.search('국내산 재료') and not pattern.search('맛있는 커피')


def test_prices_tolerate_a_misread_won_but_ignore_bare_numbers():
    assert compare.prices(words('25,0002!')) == {25000}
    assert compare.prices(words('4500', '원')) == {4500}
    assert compare.prices(words('2026', '오픈')) == set()


def test_right_price_survives_a_won_read_as_digits():
    assert compare.has_price(words('2500074'), 25000)
    assert compare.has_price(words('25,000원'), 25000)
    assert not compare.has_price(words('2500074'), 22000)
    assert compare.prices(words('2500074')) == set()  # never counted as a wrong price either


def test_names_match_without_spaces_and_report_similarity():
    assert compare.contains(words('골', '목', '카페'), '골목카페') == (True, 1.0)
    ok, similarity = compare.contains(words('골목까페'), '골목카페')
    assert not ok and 0.7 < similarity < 1


def test_claims_flag_only_what_the_facts_do_not_support():
    found = compare.claims(words('인기', '1위', '수제', '커피', '30%', '할인'), CASE, compare.claim_pattern())
    assert found == ['1위', '30%', '인기', '할인']  # 수제 is in the product features


def test_price_boxes_pick_the_price_words():
    ws = [Word('4,500', (10, 10, 50, 30)), Word('원', (52, 10, 70, 30)), Word('2026', (0, 80, 40, 100))]
    assert compare.price_boxes(ws, '4,500원') == [(10, 10, 50, 30)]


def test_edit_change_counts_only_pixels_outside_the_price():
    before = textured((400, 500))
    after = before.copy()
    ImageDraw.Draw(after).rectangle((100, 400, 300, 460), fill='white')
    same = compare.edit_change(before, after, [(100, 400, 300, 460)])
    assert same['changed_outside_price'] == 0 and same['ssim_outside_price'] > 0.99
    moved = compare.edit_change(before, before.transform(before.size, Image.AFFINE, (1, 0, 12, 0, 1, 0)), [(100, 400, 300, 460)])
    assert moved['changed_outside_price'] > 0.3 and moved['ssim_outside_price'] < 0.9
    resized = compare.edit_change(before, after.resize((200, 250)), [])
    assert resized['size_changed'] and not resized['price_area_found']


def test_keypoints_separate_the_same_photo_from_a_repainted_one():
    photo = textured()
    def ad(product, width):
        canvas = Image.new('RGB', (1080, 1350), 'white')
        canvas.paste(product.resize((width, width * 3 // 4)), (300, 500))
        return canvas
    assert compare.keypoint_inliers(photo, ad(photo, 240)) >= compare.INLIER_PASS
    repainted = photo.filter(ImageFilter.ModeFilter(15)).rotate(10)
    assert compare.keypoint_inliers(photo, ad(repainted, 600)) < compare.INLIER_PASS


def test_summary_puts_hanjang_first_and_counts_cases():
    rows = [{'system': name, 'price_ok': ok, 'wrong_prices': [] if ok else [4900], 'store_name_ok': True,
             'product_name_ok': True, 'unsupported_claims': [] if ok else ['인기'], 'product_kept': ok,
             'product_inliers': 300 if ok else 10, 'make_seconds': 15.0, 'edit_seconds': 3.0, 'cost_usd': 0.0}
            for name, ok in (('chatgpt', False), ('hanjang', True))]
    table = compare.summary(rows)
    assert table.splitlines()[0] == '| 항목 | hanjang | chatgpt |'
    assert '| 가격 정확 (광고 수) | 1/1 | 0/1 |' in table


def korean_ocr():
    if not shutil.which('tesseract'):
        return False
    return 'kor' in subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True).stdout


@pytest.mark.skipif(not korean_ocr(), reason='Tesseract with Korean data is not installed')
def test_measure_reads_a_rendered_ad(tmp_path):
    font = ImageFont.truetype(str(ROOT / 'templates' / 'fonts' / 'NotoSansKR-Bold.otf'), 72)
    photo = textured()
    photo.save(tmp_path / 'photo.png')
    ad = Image.new('RGB', (1080, 1350), (245, 238, 228))
    ad.paste(photo.resize((480, 360)), (300, 420))
    draw = ImageDraw.Draw(ad)
    draw.text((80, 80), '골목카페', fill='black', font=font)
    draw.text((80, 200), '아메리카노', fill='black', font=font)
    draw.text((80, 900), '인기 1위', fill='black', font=font)
    draw.text((80, 1100), '4,900원', fill='black', font=font)
    ad.save(tmp_path / 'ad.png')
    row = {'system': 'other', 'ad_image': 'ad.png', 'make_seconds': '40'}
    out = compare.measure_one({**CASE, 'photo': str(tmp_path / 'photo.png')}, row, tmp_path, compare.claim_pattern())
    assert out['store_name_ok'] and out['product_name_ok']
    assert not out['price_ok'] and out['wrong_prices'] == [4900]
    assert '인기' in out['unsupported_claims']  # OCR may read 1위 as 19; number claims are unit-tested above
    assert out['product_kept']
