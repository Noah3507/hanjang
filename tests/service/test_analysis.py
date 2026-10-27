from datetime import timedelta
from io import BytesIO
from pathlib import Path
import subprocess
import sys
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from app.config import Settings
from app.main import create_app
from app.services.analysis_palette import extract_palette
from app.services.analysis_execution import AnalysisExecution
from app.services.uploads import now

def png(mode='RGB', color=(120, 60, 180), size=(300, 300)):
    stream = BytesIO()
    Image.new(mode, size, color).save(stream, 'PNG')
    return stream.getvalue()

@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(_env_file=None, upload_root=tmp_path / 'uploads'))
    calls = []
    def fake(data):
        calls.append(data)
        return {'clip': {'status': 'available', 'cues': [dict(category='category', candidate_id='food', label='단서', similarity=0.2)]}}
    app.state.analysis_store.executor = fake
    with TestClient(app) as client:
        headers = {'X-Hanjang-Session': client.post('/api/v1/sessions').json()['session_token']}
        data = png()
        upload = client.post('/api/v1/uploads', headers=headers, files={'photo': ('a.png', data, 'image/png')}).json()
        path = f'/api/v1/jobs/{upload["job_id"]}/photo-analysis'
        yield app, client, headers, upload, path, calls, data

def test_analysis_preserves_facts_original_reuses_and_protects(setup):
    app, client, headers, meta, path, calls, data = setup
    draft = {'facts': {'store_name': '  가게 ', 'product_name': '원본 상품', 'price_text': ' 1,000 원 '}, 'mood': 'warm'}
    client.put(path.replace('photo-analysis', 'input'), headers=headers, json=draft)
    assert client.get(path, headers=headers).json()['status'] == 'pending'
    response = client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    assert response.status_code == 202 and response.json()['status'] == 'processing'
    assert response.headers['location'] == path
    result = client.get(path, headers=headers)
    assert result.headers['cache-control'] == 'no-store'
    body = result.json()
    assert body['is_current'] and body['status'] == 'completed'
    assert body['clip']['score_type'] == 'cosine_similarity'
    assert body['palette']['colors'][0]['hex'] == '#783CB4'
    assert body['expires_at'] == meta['expires_at']
    assert client.get(path.replace('photo-analysis', 'input'), headers=headers).json()['facts'] == {**draft['facts'], 'address': None, 'instagram_handle': None}
    assert client.get('/api/v1/assets/'+meta['asset_id'], headers=headers).content == data
    assert client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']}).json()['status'] == 'completed'
    assert len(calls) == 1
    assert client.post(path, headers=headers, json={'expected_asset_id': '0'*32}).status_code == 409
    assert client.post(path, headers=headers, json={'expected_asset_id': '../../x'}).status_code == 422
    assert client.get(path).status_code == 401
    other = {'X-Hanjang-Session': client.post('/api/v1/sessions').json()['session_token']}
    assert client.get(path, headers=other).status_code == 404
    assert client.get('/api/v1/jobs/missing/photo-analysis', headers=headers).status_code == 404
    record = app.state.upload_store.records[meta['job_id']]
    record.upload.expires_at = now() - timedelta(seconds=1)
    assert client.get(path, headers=headers).status_code == 410
    app.state.upload_store.cleanup()
    assert meta['job_id'] not in app.state.upload_store.records

def test_source_snapshot_stale_context_and_new_source(setup):
    from app.services.photo_processor import process_photo
    app, client, headers, meta, path, calls, data = setup
    def mask(im):
        result = Image.new('L', im.size, 0)
        result.paste(255, (50, 50, 250, 250))
        return result
    app.state.photo_processor = lambda data: process_photo(data, mask)
    client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    client.post(path.replace('photo-analysis', 'photo-processing'), headers=headers)
    state = client.get(path.replace('photo-analysis', 'photo-processing'), headers=headers).json()
    asset = state['processed']['asset_id']
    client.put(path.replace('photo-analysis', 'photo-source'), headers=headers, json={'photo_source': 'processed'})
    previous = client.get(path, headers=headers).json()
    assert not previous['is_current'] and previous['source_asset_id'] == meta['asset_id']
    owner = app.state.upload_store.authenticate(headers['X-Hanjang-Session'])
    assert app.state.analysis_store.context(owner, meta['job_id']) is None
    assert client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']}).status_code == 409
    assert client.post(path, headers=headers, json={'expected_asset_id': asset}).status_code == 202
    assert client.get(path, headers=headers).json()['is_current']
    assert app.state.analysis_store.context(owner, meta['job_id']) is not None
    assert len(app.state.upload_store.records[meta['job_id']].analyses) == 2

@pytest.mark.parametrize('warning', ['ANALYSIS_MODEL_UNAVAILABLE', 'ANALYSIS_MODEL_INVALID', 'ANALYSIS_WORKER_FAILED', 'ANALYSIS_TIMEOUT'])
def test_clip_failure_keeps_palette(setup, warning):
    app, client, headers, meta, path, calls, data = setup
    app.state.analysis_store.executor = lambda data: {'clip': {'status': 'unavailable'}, 'warning': warning}
    client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    result = client.get(path, headers=headers).json()
    assert result['status'] == 'completed' and result['clip']['status'] == 'unavailable'
    assert result['palette']['status'] == 'available' and result['warnings'] == [warning]

def test_bad_clip_numbers_do_not_publish(setup):
    app, client, headers, meta, path, calls, data = setup
    app.state.analysis_store.executor = lambda data: {'clip': {'status': 'available', 'cues': [dict(category='category', candidate_id='bad', label='bad', similarity=float('nan'))]}}
    client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    result = client.get(path, headers=headers).json()
    assert result['clip']['status'] == 'unavailable' and result['palette']['status'] == 'available'

def test_busy_dedup_and_expiry_during_worker(setup):
    app, client, headers, meta, path, calls, data = setup
    store = app.state.analysis_store
    owner = app.state.upload_store.authenticate(headers['X-Hanjang-Session'])
    first, run = store.start(owner, meta['job_id'], meta['asset_id'])
    assert run
    assert not store.start(owner, meta['job_id'], meta['asset_id'])[1]
    other = client.post('/api/v1/uploads', headers=headers, files={'photo': ('a.png', data, 'image/png')}).json()
    with pytest.raises(Exception) as error:
        store.start(owner, other['job_id'], other['asset_id'])
    assert error.value.status == 503
    def expired(data):
        app.state.upload_store.records[meta['job_id']].upload.expires_at = now()-timedelta(seconds=1)
        return {'clip': {'status': 'unavailable'}}
    store.executor = expired
    store.finish(owner, meta['job_id'], meta['asset_id'])
    assert not store.active and client.get(path, headers=headers).status_code == 410

def test_invalid_file_failure_preserves_original(setup):
    app, client, headers, meta, path, calls, data = setup
    app.state.upload_store.records[meta['job_id']].path.write_bytes(b'broken')
    client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    body = client.get(path, headers=headers).json()
    assert body['status'] == 'failed' and body['error']['code'] == 'ANALYSIS_FAILED'
    assert len(calls) == 0

def test_fully_transparent_image_is_neutral_failure(setup):
    app, client, headers, meta, path, calls, data = setup
    app.state.upload_store.records[meta['job_id']].path.write_bytes(png('RGBA', (255, 0, 0, 0)))
    client.post(path, headers=headers, json={'expected_asset_id': meta['asset_id']})
    body = client.get(path, headers=headers).json()
    assert body['status'] == 'failed' and body['clip']['cues'] == []
    assert body['palette']['colors'] == [] and 'ANALYSIS_NO_VISIBLE_PIXELS' in body['warnings']
    assert not calls

def test_palette_transparency_seed_and_proportions():
    image = Image.new('RGBA', (100, 100), (0, 255, 0, 0))
    image.paste((255, 0, 0, 255), (0, 0, 50, 50))
    image.paste((0, 0, 255, 255), (50, 0, 100, 50))
    stream = BytesIO(); image.save(stream, 'PNG')
    a = extract_palette(stream.getvalue())
    assert a == extract_palette(stream.getvalue())
    assert {c.hex for c in a.colors} == {'#FF0000', '#0000FF'}
    assert sum(c.proportion for c in a.colors) == pytest.approx(1)
    assert all(c.proportion == pytest.approx(.5, abs=.03) for c in a.colors)
    assert extract_palette(png('RGBA', (255, 0, 0, 0))).status == 'unavailable'
    with pytest.raises(Exception):
        extract_palette(b'not an image')

def test_missing_environment_and_model(tmp_path):
    executor = AnalysisExecution(tmp_path/'python', tmp_path/'model')
    assert executor(b'x')['warning'] == 'ANALYSIS_MODEL_UNAVAILABLE'
    (tmp_path/'model').write_bytes(b'x')
    assert executor(b'x')['warning'] == 'ANALYSIS_ENV_UNAVAILABLE'
    executor.close()

@pytest.mark.parametrize('mode', ['reuse', 'timeout', 'wrong-id', 'exit'])
def test_real_subprocess_protocol_cleanup_and_timeout(tmp_path, monkeypatch, mode):
    import app.services.analysis_execution as execution
    model = tmp_path/'model'; model.write_bytes(b'test')
    real_popen = subprocess.Popen
    script = """import json,sys,time,os
for line in sys.stdin:
 m=json.loads(line)
 MODE
 print(json.dumps({'request_id':m['request_id'],'clip':{'status':'unavailable'},'worker_pid':os.getpid()}),flush=True)
""".replace('MODE', {'reuse': 'pass', 'timeout': 'time.sleep(10)', 'wrong-id': "m['request_id']='wrong'", 'exit': 'sys.exit(1)'}[mode])
    calls = []
    def spawn(args, **kwargs):
        process = real_popen([sys.executable, '-u', '-c', script], **kwargs)
        calls.append(process)
        return process
    monkeypatch.setattr(execution.subprocess, 'Popen', spawn)
    # taskkill uses Popen too; use the real runner through a temporary restore.
    real_run = subprocess.run
    def run(*args, **kwargs):
        monkeypatch.setattr(execution.subprocess, 'Popen', real_popen)
        try:
            return real_run(*args, **kwargs)
        finally:
            monkeypatch.setattr(execution.subprocess, 'Popen', spawn)
    monkeypatch.setattr(execution.subprocess, 'run', run)
    executor = AnalysisExecution(Path(sys.executable), model, timeout=.2 if mode == 'timeout' else 5, idle=10)
    try:
        result = executor(b'bytes')
        if mode == 'reuse':
            assert result['worker_pid'] == executor(b'other')['worker_pid']
            assert len(calls) == 1
        else:
            assert result['warning'] == ('ANALYSIS_TIMEOUT' if mode == 'timeout' else 'ANALYSIS_WORKER_FAILED')
            assert executor.process is None
    finally:
        executor.close()
    assert all(process.poll() is not None for process in calls)

def test_real_invalid_checksum_never_loads_model(tmp_path):
    model = tmp_path/'invalid.pt'; model.write_bytes(b'not official weights')
    executor = AnalysisExecution(Path(sys.executable), model, timeout=10)
    try:
        assert executor(png())['warning'] == 'ANALYSIS_MODEL_INVALID'
        assert executor.process is None
    finally:
        executor.close()
