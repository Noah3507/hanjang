"""Launcher failures must not start servers, install packages, or overwrite config."""
import json
import os
from pathlib import Path
import subprocess
import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell launcher')
SCRIPT = Path('scripts/service_local.ps1').resolve()


def run(config):
    return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SCRIPT),
        '-ConfigFile',str(config),'-CheckOnly'],capture_output=True,timeout=30)


def test_missing_config_requires_explicit_setup(tmp_path):
    config=tmp_path/'missing.json'; result=run(config)
    assert result.returncode != 0 and b'Local config missing' in result.stderr
    assert not config.exists()


def test_invalid_resource_root_preserves_config(tmp_path):
    config=tmp_path/'config.json'; content=json.dumps({'resource_root':str(tmp_path/'missing')})
    config.write_text(content);result=run(config)
    assert result.returncode != 0 and b'resource_root' in result.stderr
    assert config.read_text()==content


def test_missing_python_does_not_install_or_overwrite(tmp_path):
    config=tmp_path/'config.json'; content=json.dumps({'resource_root':str(tmp_path)})
    config.write_text(content);result=run(config)
    assert result.returncode != 0 and b'service_python' in result.stderr
    assert config.read_text()==content and not (tmp_path/'.venv').exists()
