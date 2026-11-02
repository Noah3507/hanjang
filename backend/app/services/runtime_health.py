"""Configuration readiness only. No paid requests, model downloads, or inference."""
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from app.services.render_execution import ROOT, FONT_HASH


def inspect_runtime(settings):
    checks={}
    try:
        settings.upload_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryFile(dir=settings.upload_root) as stream: stream.write(b'probe')
        checks['storage']=True
    except OSError: checks['storage']=False
    try: checks['font']=sha256((ROOT/'templates/fonts/NotoSansKR-Regular.otf').read_bytes()).hexdigest()==FONT_HASH
    except OSError: checks['font']=False
    checks['frontend']=settings.frontend_dist is None or (settings.frontend_dist/'index.html').is_file()
    checks['node']=shutil.which('node') is not None
    checks['chromium']=False
    if checks['node']:
        try:
            script="const {chromium}=require(process.argv[1]);process.stdout.write(chromium.executablePath())"
            result=subprocess.run(['node','-e',script,str(ROOT/'frontend/node_modules/playwright')],capture_output=True,timeout=5)
            checks['chromium']=result.returncode==0 and Path(result.stdout.decode().strip()).is_file()
        except (OSError,subprocess.TimeoutExpired,UnicodeError): pass
    models={'photo':settings.photo_model_path.is_file(),
        'analysis':settings.analysis_model_path.is_file() and settings.analysis_python.is_file(),
        'ranking':bool(settings.ranking_model_path and settings.ranking_model_path.is_file() and settings.ranking_python.is_file())}
    checks['models']=all(models.values()) and settings.ranking_mode=='model' if settings.release_require_models else True
    checks['copy_config']=settings.copy_provider=='mock' or bool(settings.copy_allow_paid and settings.openai_api_key and settings.openai_api_key.get_secret_value())
    return {'status':'ready' if all(checks.values()) else 'not_ready','check_level':'configuration_not_inference',
        'checks':checks,'models_configured':models,'copy_provider':settings.copy_provider,'ranking_mode':settings.ranking_mode}


class RuntimeHealth:
    def __init__(self,settings):self.settings=settings;self.cached=None;self.checked=0.
    def get(self):
        if self.cached is None or time.monotonic()-self.checked>30:
            self.cached=inspect_runtime(self.settings);self.checked=time.monotonic()
        return self.cached
