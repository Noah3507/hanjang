"""Production model selection is explicit, offline and integrity checked."""
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
import pytest

from app.config import Settings
from app.services.photo_models import MODELS, model_file_verified


@pytest.mark.parametrize('name', ['u2netp', 'u2net'])
def test_readiness_verifies_named_weights_and_replacement(tmp_path, monkeypatch, name):
    path = tmp_path/'weights.onnx';content = b'verified-model'
    monkeypatch.setitem(MODELS, name, replace(MODELS[name], size=len(content), sha256=sha256(content).hexdigest()))
    assert not model_file_verified(path, name)
    path.write_bytes(content)
    assert model_file_verified(path, name)
    path.write_bytes(b'corrupted-file')  # same length, different checksum
    assert len(path.read_bytes()) == len(content)
    assert not model_file_verified(path, name)
    path.write_bytes(content)
    assert model_file_verified(path, name)
    other = 'u2net' if name == 'u2netp' else 'u2netp'
    assert not model_file_verified(path, other)


def test_readiness_rejects_wrong_name_or_file_without_loading_model(tmp_path, monkeypatch):
    from app.services.runtime_health import inspect_runtime
    path = tmp_path/'u2net.onnx';path.write_bytes(b'not-weights')
    settings = Settings(_env_file=None, upload_root=tmp_path/'uploads', photo_model_name='u2net',
                        photo_model_path=path, release_require_models=True)
    result = inspect_runtime(settings)
    assert not result['models_configured']['photo'] and result['status'] == 'not_ready'
    assert str(path) not in str(result)
    assert path.read_bytes() == b'not-weights'
    assert not model_file_verified(path, 'unknown')


def test_photo_check_cli_never_prints_private_path(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('photo_check', Path('scripts/service_check_photo_model.py'))
    tool = importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    path = tmp_path/'private-name.onnx'
    monkeypatch.setattr(sys, 'argv', ['check', '--model', 'u2net', '--path', str(path)])
    assert tool.main() == 1
    assert str(path) not in capsys.readouterr().out and not path.exists()
    monkeypatch.setattr(tool, 'model_file_verified', lambda p, name: p == path and name == 'u2net')
    assert tool.main() == 0
    assert 'u2net' in capsys.readouterr().out


def test_windows_launchers_restore_model_selection_and_probe_uses_name():
    for name in ('service_local.ps1', 'service_presentation.ps1'):
        source = (Path('scripts')/name).read_text(encoding='utf-8')
        names = source.split('$names', 1)[1].split('$previous', 1)[0]
        assert 'HANJANG_PHOTO_MODEL_NAME' in names and 'HANJANG_PHOTO_MATTE_MODE' in names
        assert 'config.photo_model_name' in source and 'config.photo_matte_mode' in source
        assert 'foreach' in source.split('finally')[-1]
    probe = Path('scripts/service_model_check.py').read_text(encoding='utf-8')
    assert "os.environ.get('HANJANG_PHOTO_MODEL_NAME', 'u2netp')" in probe
    assert Settings(_env_file=None).photo_model_name == 'u2netp'


def test_model_probe_passes_selected_model_to_offline_loader(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('model_probe', Path('scripts/service_model_check.py'))
    probe = importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    monkeypatch.setenv('HANJANG_PHOTO_MODEL_NAME', 'u2net')
    for name in ('PHOTO_MODEL_PATH', 'ANALYSIS_PYTHON', 'ANALYSIS_MODEL_PATH'):
        monkeypatch.setenv('HANJANG_'+name, str(tmp_path/name))
    seen=[]
    def loader(path, name):
        assert path == tmp_path/'PHOTO_MODEL_PATH';seen.append(name)
        return lambda image: image.getchannel('R')
    class Analysis:
        def __init__(self, *args):pass
        def __call__(self, raw):return {'clip':{'status':'available'}}
        def close(self):seen.append('closed')
    monkeypatch.setattr(probe, 'LocalRembg', loader)
    monkeypatch.setattr(probe, 'AnalysisExecution', Analysis)
    probe.main()
    assert seen == ['u2net','closed']
