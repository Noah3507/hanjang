"""Jinja2 binds escaped text; isolated Node/Playwright renders offline pages."""
import base64
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageOps
from app.services.copy_glyphs import font_text_supported

ROOT = Path(__file__).resolve().parents[3]
VERSION = 'four-layouts-v1'
FONT_HASH = '69975a0ac8472717870aefeab0a4d52739308d90856b9955313b2ad5e0148d68'
ORDERS = ('emotional', 'price', 'visual', 'brand')

class RenderFailure(Exception):
    def __init__(self, code):
        self.code = code

def opaque_png(data):
    with Image.open(BytesIO(data)) as image:
        image.load()
        if image.format != 'PNG' or image.size != (1080, 1350):
            raise RenderFailure('RENDER_INVALID_PNG')
        if image.mode == 'RGBA' and image.getchannel('A').getextrema() != (255, 255):
            raise RenderFailure('RENDER_INVALID_PNG')
        if image.mode not in ('RGB', 'RGBA'):
            raise RenderFailure('RENDER_INVALID_PNG')
        output = BytesIO(); image.convert('RGB').save(output, 'PNG')
        return output.getvalue()

class RenderExecution:
    def __init__(self, timeout=90):
        self.timeout = timeout

    def __call__(self, draft, copy, photo):
        # Never rewrite user facts. Stop before launching Chromium with a safe error.
        try:
            font = (ROOT/'templates/fonts/NotoSansKR-Regular.otf').read_bytes()
            if sha256(font).hexdigest() != FONT_HASH:
                raise ValueError('Invalid font')
            # The cmap reader validates the same pinned artifact.
            from app.services.copy_glyphs import supported_codepoints
            supported_codepoints()
        except Exception:
            raise RenderFailure('RENDER_FONT_UNAVAILABLE') from None
        if any(value and not font_text_supported(value) for value in draft.facts.model_dump().values()):
            raise RenderFailure('RENDER_UNSUPPORTED_GLYPH')
        css = (ROOT/'templates/tokens.css').read_text(encoding='utf-8')
        css += "@font-face{font-family:HanjangNoto;src:url(data:font/otf;base64,"+base64.b64encode(font).decode()+");font-weight:100 900;font-display:block}"
        # EXIF orientation is display interpretation; never mutate stored original.
        with Image.open(BytesIO(photo)) as source:
            image = ImageOps.exif_transpose(source).convert('RGBA')
            stream = BytesIO(); image.save(stream, 'PNG')
        uri = 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
        env = Environment(loader=FileSystemLoader(ROOT/'templates'), autoescape=select_autoescape(['html']), undefined=StrictUndefined)
        pages = []
        for variant in copy.variants:
            if variant.strategy not in ORDERS:
                raise RenderFailure('RENDER_INVALID_TEMPLATE')
            template = env.get_template(variant.strategy+'.html')
            texts = {**draft.facts.model_dump(), **variant.ad_copy.model_dump()}
            pages.append({'strategy': variant.strategy, 'html': template.render(css=css, texts=texts,
                strategy=variant.strategy, mood=draft.mood, photo=uri)})
        node = shutil.which('node') or (r'C:\Program Files\nodejs\node.exe' if os.name == 'nt' else 'node')
        process = subprocess.Popen([node, str(ROOT/'scripts/service_render_worker.mjs')], cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt')
        try:
            stdout, _ = process.communicate(json.dumps({'pages': pages}).encode(), timeout=self.timeout)
            body = json.loads(stdout)
            if process.returncode or body.get('error'):
                raise RenderFailure(body.get('error', 'RENDER_FAILED'))
            results = body['results']
            if len(results) != len(copy.variants) or {r['strategy'] for r in results} != {v.strategy for v in copy.variants}:
                raise RenderFailure('RENDER_INVALID_RESULT')
            for result in results:
                result['png'] = opaque_png(base64.b64decode(result['png'], validate=True))
            return results
        except subprocess.TimeoutExpired:
            raise RenderFailure('RENDER_TIMEOUT') from None
        except RenderFailure:
            raise
        except Exception:
            raise RenderFailure('RENDER_FAILED') from None
        finally:
            # Own worker tree only; never touch user's browser or dev servers.
            if process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()

def rgb(value):
    import re
    values = re.findall(r'[\d.]+', value)
    return '#'+''.join(f'{int(float(n)):02X}' for n in values[:3])
