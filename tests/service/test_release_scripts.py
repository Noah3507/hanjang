"""Opt-in safeguards: invoking scripts must not silently make paid/remote calls."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
def script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_paid_smoke_default_is_plan_only(monkeypatch,capsys):
    module=script('service_openai_smoke')
    monkeypatch.setattr(sys,'argv',['smoke'])
    assert module.main()==0
    output=capsys.readouterr().out
    assert 'plan_only' in output and '"requests_max": 1' in output

def test_paid_smoke_requires_separate_approval(monkeypatch,capsys):
    module=script('service_openai_smoke')
    monkeypatch.setattr(sys,'argv',['smoke','--execute'])
    assert module.main()==2
    assert 'approval flag missing' in capsys.readouterr().out

def test_approved_smoke_uses_existing_provider_once_with_fake_only(monkeypatch,capsys):
    from types import SimpleNamespace
    from app.services.copy_provider import MockCopyProvider
    import app.config
    import app.services.copy_provider
    class Fake(MockCopyProvider):
        calls=0;closed=False
        def generate(self,payload):
            self.calls+=1
            assert 'address' not in payload and not payload['visual_hints']
            return super().generate(payload)
        def close(self):self.closed=True
    fake=Fake()
    monkeypatch.setattr(app.config,'Settings',lambda **kwargs:SimpleNamespace(copy_provider='openai',copy_allow_paid=True,openai_api_key='synthetic-fake-key'))
    monkeypatch.setattr(app.services.copy_provider,'build_copy_provider',lambda settings:fake)
    monkeypatch.setattr(sys,'argv',['smoke','--execute','--approved-paid-call'])
    assert script('service_openai_smoke').main()==0
    output=capsys.readouterr().out
    assert '"status": "passed"' in output and 'Synthetic product' not in output
    assert fake.calls==1 and fake.closed

@pytest.mark.parametrize('url',['https://outside.example','http://outside.example','http://user:secret@localhost:8014','http://localhost:8014/?secret=x'])
def test_remote_smoke_rejects_before_network(monkeypatch,url):
    module=script('service_deploy_smoke')
    monkeypatch.setattr(sys,'argv',['smoke','--url',url])
    def forbidden(*args,**kwargs):pytest.fail('Network must not run')
    monkeypatch.setattr(module.urllib.request,'urlopen',forbidden)
    assert module.main()==2
