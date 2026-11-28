"""A-side worker placement and source fencing; B's template files remain untouched."""
from io import BytesIO
import os
from pathlib import Path

from PIL import Image
import pytest

from app.services import template_v3
from app.services.template_v3 import TemplateInput, render_templates
from test_rendering import service
from test_designs import designs, generate, snap

TARGETS = ['price_a', 'price_c', 'emotional_d', 'brand_a', 'brand_b']


def test_worker_is_part_of_fingerprint_without_changing_b_limits(tmp_path, monkeypatch):
    folder = tmp_path/'templates/v3'
    folder.mkdir(parents=True)
    for name in ('base.html', 'price.css', 'collection.css', 'quality.css'):
        (folder/name).write_text(name, encoding='utf-8')
    worker = tmp_path/'scripts/service_render_v3_worker.mjs'
    worker.parent.mkdir()
    worker.write_text('before', encoding='utf-8')
    monkeypatch.setattr(template_v3, 'ROOT', tmp_path)
    before = template_v3.template_fingerprint()
    worker.write_text('after worker update', encoding='utf-8')
    assert template_v3.template_fingerprint() != before
    # A does not write B's measured limits or change their HTML/CSS source hash.
    assert not (folder/'limits.json').exists()


def test_worker_update_stales_design_rank_and_download_without_copy_calls(designs, monkeypatch, tmp_path):
    folder = tmp_path/'templates/v3'
    folder.mkdir(parents=True)
    for name in ('base.html', 'price.css', 'collection.css', 'quality.css'):
        (folder/name).write_text(name, encoding='utf-8')
    worker = tmp_path/'scripts/service_render_v3_worker.mjs'
    worker.parent.mkdir()
    worker.write_text('before', encoding='utf-8')
    monkeypatch.setattr(template_v3, 'ROOT', tmp_path)
    app, client, headers, _, base, body, v2 = designs
    path, state = generate(designs)
    assert client.post(path+'/ranking', headers=headers, json=snap(state)).status_code == 200
    copy = client.get(base+'/copy-generation', headers=headers).json()
    monkeypatch.setattr(app.state.copy_store.provider, 'generate', lambda *a: pytest.fail('No LLM call on worker change'))
    worker.write_text('updated placement', encoding='utf-8')
    latest = client.get(path, headers=headers).json()
    assert not latest['is_current'] and latest['ranking'] is None
    candidate = state['candidates'][0]
    assert client.get(path+'/candidates/'+candidate['candidate_id']+'/download', headers=headers,
                      params={'format':'png', **snap(state)}).status_code == 409
    assert client.post(path, headers=headers, json=body).status_code == 202
    assert client.get(path, headers=headers).json()['is_current']
    assert client.get(base+'/copy-generation', headers=headers).json()['copy_key'] == copy['copy_key']
    assert client.get(base+'/rendering', headers=headers).json() == v2


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
@pytest.mark.parametrize('size', [(900,400), (400,900), (600,600)])
def test_original_rectangle_uses_frame_and_cutout_keeps_ellipse(size):
    data = TemplateInput('테스트 가게', '상품 사진', '10,500원', '사진 그대로', '', '')
    for mode in ('RGB', 'RGBA'):
        image = Image.new(mode, size, (90,140,160) if mode == 'RGB' else (90,140,160,255))
        if mode == 'RGBA':image.putpixel((0,0), (0,0,0,0))
        buffer = BytesIO();image.save(buffer, 'PNG')
        for row in render_templates(data, buffer.getvalue(), TARGETS, timeout=180):
            measure = row['measurement'];placement = measure['image_placement']
            assert placement['policy'] == ('rectangle-safe' if mode == 'RGB' else 'alpha-ellipse-safe')
            assert not placement['unintended_clip']
            if mode == 'RGB':
                box = placement['subject_bbox'];frame = measure['photo_frame']
                assert box['width']/box['height'] == pytest.approx(size[0]/size[1])
                assert max(box['width']/frame['width'], box['height']/frame['height']) > .93
                assert not measure['text_collisions'] and not any(t['overflow'] for t in measure['text'])
            with Image.open(BytesIO(row['png'])) as result:
                assert result.mode == 'RGB' and result.size == (1080,1350)
