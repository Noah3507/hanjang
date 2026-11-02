"""Presentation security and lifecycle checks; no network/model downloads."""
import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.config import Settings
from app.main import create_app
from app.services.presentation import PresentationGateway
from app.ml_adapter.real_ranker import RealRanker

PASSWORD='synthetic-presentation-password-only'

def configured(tmp_path, **kwargs):
    return Settings(_env_file=None,upload_root=tmp_path/'uploads',copy_provider='mock',
        ranking_mode='mock',presentation_password=SecretStr(PASSWORD),**kwargs)

def test_gateway_auth_origin_and_security(tmp_path):
    app=create_app(configured(tmp_path))
    with TestClient(PresentationGateway(app,configured(tmp_path))) as client:
        assert client.get('/health').status_code==401
        assert client.get('/health',headers={'Authorization':'Basic !!!'}).status_code==401
        assert client.get('/health',auth=('presenter','wrong')).status_code==401
        good=client.get('/health',auth=('presenter',PASSWORD))
        assert good.status_code==200
        assert good.headers['x-frame-options']=='DENY'
        assert "script-src 'self'" in good.headers['content-security-policy']
        assert PASSWORD not in good.text
        assert client.post('/api/v1/jobs',auth=('presenter',PASSWORD),headers={'Origin':'https://evil.example'}).status_code==403
        # Gateway credentials do not bypass job ownership/session protection.
        assert client.get('/api/v1/jobs/not-a-job',auth=('presenter',PASSWORD)).status_code in (401,404,422)

def test_gateway_rate_limit_recovers_without_restart(tmp_path):
    now=[0.]
    settings=configured(tmp_path,presentation_requests_per_minute=30,presentation_mutations_per_minute=1)
    with TestClient(PresentationGateway(create_app(settings),settings,clock=lambda:now[0])) as client:
        auth=('presenter',PASSWORD)
        assert client.post('/missing',auth=auth).status_code==404
        limited=client.post('/missing',auth=auth)
        assert limited.status_code==429 and limited.headers['retry-after']=='60'
        now[0]=61
        assert client.post('/missing',auth=auth).status_code==404
        for _ in range(20):assert client.get('/health').status_code==401
        assert client.get('/health').status_code==429
        now[0]=122
        assert client.get('/health').status_code==401

def test_gateway_requires_strong_local_secret(tmp_path):
    with pytest.raises(ValueError,match='20 characters'):
        PresentationGateway(None,Settings(_env_file=None,presentation_password=SecretStr('short')))

def test_static_frontend_does_not_expose_private_files(tmp_path):
    dist=tmp_path/'dist';dist.mkdir();(dist/'index.html').write_text('<h1>Built app</h1>')
    settings=configured(tmp_path,frontend_dist=dist)
    app=create_app(settings)
    app.state.runtime_health.get=lambda:{'status':'ready','check_level':'configuration_not_inference'}
    with TestClient(app) as client:
        assert 'Built app' in client.get('/').text
        assert client.get('/health').json()['status']=='ok'
        assert client.get('/ready').status_code==200
        app.state.cleanup_failed=True
        assert client.get('/ready').status_code==503
        for path in ('/.env','/uploads/secret.png','/artifacts/models/model.safetensors'):
            assert client.get(path).status_code==404

def test_readiness_configuration_is_not_inference(tmp_path,monkeypatch):
    import app.services.runtime_health as module
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:type('Result',(),{'returncode':0,'stdout':os.fsencode(__file__)})())
    monkeypatch.setattr(module.shutil,'which',lambda name:'node')
    settings=configured(tmp_path,release_require_models=True,photo_model_path=tmp_path/'absent.onnx')
    result=module.inspect_runtime(settings)
    assert result['status']=='not_ready'
    assert result['check_level']=='configuration_not_inference'
    assert result['models_configured']['photo'] is False
    assert str(tmp_path) not in str(result) and PASSWORD not in str(result)

def test_expired_snapshot_cleanup_preserves_unknown_and_recent(tmp_path):
    ranker=RealRanker(Path('python'),None,tmp_path)
    for name,old,marked,unknown in [('ranking-aaaaaaaa',True,True,False),('ranking-bbbbbbbb',False,True,False),
            ('ranking-cccccccc',True,False,False),('ranking-dddddddd',True,True,True)]:
        folder=tmp_path/name;folder.mkdir();(folder/'0.png').write_bytes(b'owned')
        if marked:(folder/'.hanjang-snapshot').write_bytes(b'owned-snapshot-v1')
        if unknown:(folder/'user.txt').write_text('preserve')
        if old:os.utime(folder,(time.time()-90000,)*2)
    ranker.cleanup_expired()
    assert not (tmp_path/'ranking-aaaaaaaa').exists()
    for name in ('ranking-bbbbbbbb','ranking-cccccccc','ranking-dddddddd'):assert (tmp_path/name/'0.png').is_file()

def test_cleanup_failure_does_not_prevent_startup(tmp_path,monkeypatch):
    app=create_app(configured(tmp_path))
    def denied():raise PermissionError('sensitive path must not be logged')
    monkeypatch.setattr(app.state.upload_store,'cleanup',denied)
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert app.state.cleanup_failed is True

def test_one_locked_expired_file_does_not_starve_others(tmp_path,monkeypatch):
    from app.services.uploads import PrivateUploadStore
    root=tmp_path/'uploads';root.mkdir()
    blocked=root/('a'*32+'.png');other=root/('b'*32+'.png')
    for path in (blocked,other):
        path.write_bytes(b'test');os.utime(path,(time.time()-90000,)*2)
    original=Path.unlink
    def unlink(path,*args,**kwargs):
        if path==blocked:raise PermissionError('locked fixture')
        return original(path,*args,**kwargs)
    store=PrivateUploadStore(root)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',unlink)
        with pytest.raises(OSError,match='retry'):store.cleanup()
    assert blocked.exists() and not other.exists()
    store.cleanup()
    assert not blocked.exists()
