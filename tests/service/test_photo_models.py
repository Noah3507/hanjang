from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import importlib
import importlib.util
import sys

import numpy as np
from PIL import Image
import pytest

from app.config import Settings
from app.services.photo_models import MODELS
from app.services.photo_processor import LocalRembg, process_photo, PROCESSING_VERSION


def sample():
    image = Image.new('RGBA', (100, 80), (51, 122, 210, 200))
    stream = BytesIO(); image.save(stream, 'PNG')
    return stream.getvalue()


def mask(image):
    alpha = Image.new('L', image.size, 0)
    alpha.paste(255, (30, 20, 70, 60))
    alpha.putpixel((5, 5), 40)
    alpha.putpixel((90, 75), 255)  # separated opaque accessory
    return alpha


def test_defaults_remain_legacy_and_configuration_is_explicit():
    settings = Settings(_env_file=None)
    assert settings.photo_model_name == 'u2netp' and settings.photo_matte_mode == 'cleanup'
    assert process_photo(sample(), mask).processing_version == PROCESSING_VERSION
    for kwargs in [dict(photo_model_name='remote'), dict(photo_matte_mode='automatic')]:
        with pytest.raises(ValueError): Settings(_env_file=None, **kwargs)


def test_app_passes_opt_in_configuration_without_loading_model(tmp_path):
    from app.main import create_app
    settings = Settings(_env_file=None, upload_root=tmp_path/'uploads', photo_model_name='u2net',
                        photo_model_path=tmp_path/'missing.onnx', photo_matte_mode='model-alpha')
    processor = create_app(settings).state.photo_processor
    assert processor.model_name == 'u2net' and processor.matte_mode == 'model-alpha'
    assert processor.model == tmp_path/'missing.onnx' and not processor.model.exists()


def test_raw_alpha_is_opt_in_preserves_translucency_rgb_and_original():
    raw = sample(); before = sha256(raw).hexdigest()
    cleaned = process_photo(raw, mask)
    model = process_photo(raw, mask, matte_mode='model-alpha')
    a = np.array(Image.open(BytesIO(model.png)))
    assert a[5, 5, 3] == 40 and a[75, 90, 3] == 200  # clamp original alpha
    assert np.array(Image.open(BytesIO(cleaned.png)))[5, 5, 3] == 0
    assert np.all(a[:, :, :3] == [51, 122, 210])
    assert model.processing_version != cleaned.processing_version
    assert sha256(raw).hexdigest() == before
    assert process_photo(raw, mask, matte_mode='bad').warnings == ['PHOTO_PROCESSING_FAILED']


@pytest.mark.parametrize('name', list(MODELS))
def test_pinned_offline_session_and_single_load(tmp_path, monkeypatch, name):
    content = b'local-test-model'; path = tmp_path/'model.onnx'; path.write_bytes(content)
    monkeypatch.setitem(MODELS, name, replace(MODELS[name], size=len(content), sha256=sha256(content).hexdigest()))
    loads = []
    class FakeSession:
        def __init__(self, model, options, providers):
            assert self.download_models() == str(path.resolve())
            assert model == name and providers == ['CPUExecutionProvider']
            loads.append(model)
        def predict(self, image): return [mask(image)]
    from types import SimpleNamespace
    original = importlib.import_module
    def local_import(module, *a, **kw):
        if module == 'rembg.sessions.'+MODELS[name].module:
            return SimpleNamespace(**{MODELS[name].session: FakeSession})
        return original(module, *a, **kw)
    monkeypatch.setattr(importlib, 'import_module', local_import)
    provider = LocalRembg(path, name)
    first = process_photo(sample(), provider); second = process_photo(sample(), provider)
    assert first.png == second.png and loads == [name]
    assert first.processing_version.startswith(name+'-')


@pytest.mark.parametrize('name', list(MODELS))
def test_missing_or_wrong_weights_fail_closed_without_network(tmp_path, name):
    path = tmp_path/'model.onnx'
    assert process_photo(sample(), LocalRembg(path, name)).warnings == ['PHOTO_MODEL_UNAVAILABLE']
    path.write_bytes(b'wrong-model')
    assert process_photo(sample(), LocalRembg(path, name)).warnings == ['PHOTO_PROCESSING_FAILED']
    assert path.read_bytes() == b'wrong-model'


def test_download_existing_model_is_verified_not_overwritten(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('photo_download_tool', root/'scripts/service_download_photo_model.py')
    tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
    content = b'pinned'; model = replace(MODELS['u2net'], size=len(content), sha256=sha256(content).hexdigest())
    monkeypatch.setitem(tool.MODELS, 'u2net', model); monkeypatch.setattr(tool, 'ROOT', tmp_path)
    path = tmp_path/'artifacts/models/rembg/u2net.onnx'; path.parent.mkdir(parents=True); path.write_bytes(content)
    monkeypatch.setattr(sys, 'argv', ['tool', '--download', '--model', 'u2net'])
    monkeypatch.setattr(tool.urllib.request, 'urlopen', lambda *a, **kw: pytest.fail('download forbidden'))
    tool.main(); assert path.read_bytes() == content
    path.write_bytes(b'corrupt')
    with pytest.raises(RuntimeError): tool.main()
    assert path.read_bytes() == b'corrupt'
