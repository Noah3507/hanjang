"""Opt-in local template renderer. Does not replace the four-strategy API."""
from dataclasses import dataclass, asdict
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import base64
import json
import os
import shutil
import subprocess
from uuid import uuid4

from fontTools.ttLib import TTFont
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageOps

from app.services.render_execution import ROOT, FONT_HASH, RenderFailure, opaque_png, rgb
from app.services.diagnostics_evidence import attach_contrast_evidence
from app.services.diagnostics_engine import analyze

VERSION = 'ad-templates-v3-price-1'
BOLD_HASH = '5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda'
NAMES = {'emotional': ('gallery', 'fade', 'editorial', 'door'),
         'price': ('circle', 'split', 'big-number', 'stamp'),
         'brand': ('wordmark', 'emblem', 'pattern', 'korean-wordmark'),
         'visual': ('full-bleed', 'polaroid', 'cinema', 'film')}
REGISTRY = {f'{strategy}_{letter}': {'strategy': strategy, 'variant': letter,
             'name': name, 'implemented': strategy == 'price'}
            for strategy, names in NAMES.items() for letter, name in zip('abcd', names)}


def measured_diagnostics(candidate_id, asset_id, strategy, measurement, png_hash):
    """Adapt Chromium evidence to the existing renderer/diagnostics boundary."""
    boxes = []
    for text in measurement['text']:
        box = dict(text)
        box['foreground'] = rgb(box['foreground'])
        box['background'] = None if box['background'].endswith(', 0)') else rgb(box['background'])
        boxes.append(box)
    candidate = {'candidate_id': candidate_id, 'strategy': strategy, 'png': {'asset_id': asset_id},
                 'renderer': {'text_boxes': boxes, 'product_bbox': measurement['product']}}
    return analyze(candidate, measurement, png_hash).model_dump(mode='json')


@dataclass(frozen=True)
class TemplateInput:
    store_name: str
    product_name: str
    price_text: str
    headline: str
    body: str = ''
    cta: str = ''
    discount_text: str = ''
    original_price: str = ''
    promotion_text: str = ''
    period_text: str = ''

    def validate(self):
        for name, value in asdict(self).items():
            if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
                raise RenderFailure('RENDER_INVALID_INPUT')
        if any(not getattr(self, k).strip() for k in ('store_name', 'product_name', 'price_text', 'headline')):
            raise RenderFailure('RENDER_INVALID_INPUT')


def render_templates(data: TemplateInput, photo: bytes, template_ids=None, timeout=90):
    """Four price variations by default. Raw facts/copy are never rewritten.

    Optional commercial claims must come from explicit, verified caller input.
    No LLM, disk asset store, session or existing Candidate mutations occur here.
    """
    data.validate()
    ids = list(template_ids) if template_ids is not None else [f'price_{c}' for c in 'abcd']
    if not ids or len(ids) > 16 or len(set(ids)) != len(ids) or any(
        t not in REGISTRY or not REGISTRY[t]['implemented'] for t in ids
    ):
        raise RenderFailure('RENDER_INVALID_TEMPLATE')
    text = ''.join(asdict(data).values())
    faces = []
    for filename, expected, weight in [('NotoSansKR-Regular.otf', FONT_HASH, 400),
                                        ('NotoSansKR-Bold.otf', BOLD_HASH, 700)]:
        path = ROOT / 'templates/fonts' / filename
        try:
            font = path.read_bytes()
            if sha256(font).hexdigest() != expected:
                raise ValueError('font hash')
            with TTFont(BytesIO(font)) as face:
                if any(ord(c) not in face.getBestCmap() for c in text):
                    raise RenderFailure('RENDER_UNSUPPORTED_GLYPH')
            faces.append(f"@font-face{{font-family:HanjangNoto;src:url(data:font/otf;base64,{base64.b64encode(font).decode()});font-weight:{weight};font-display:block}}")
        except RenderFailure:
            raise
        except Exception:
            raise RenderFailure('RENDER_FONT_UNAVAILABLE') from None
    try:
        with Image.open(BytesIO(photo)) as source:
            if source.width * source.height > 24_000_000:
                raise ValueError('image limit')
            image = ImageOps.exif_transpose(source).convert('RGBA')
            photo_fit = 'contain' if image.getchannel('A').getextrema()[0] < 255 else 'cover'
            stream = BytesIO()
            image.save(stream, 'PNG')
    except Exception:
        raise RenderFailure('RENDER_INVALID_IMAGE') from None
    uri = 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()
    env = Environment(loader=FileSystemLoader(ROOT/'templates/v3'),
                      autoescape=select_autoescape(['html']), undefined=StrictUndefined)
    css = (ROOT/'templates/v3/price.css').read_text(encoding='utf-8') + ''.join(faces)
    pages = [{'template_id': t, 'html': env.get_template(t+'.html').render(
        css=css, data=data, photo=uri, photo_fit=photo_fit, template_id=t)} for t in ids]
    node = shutil.which('node')
    if not node:
        raise RenderFailure('RENDER_UNAVAILABLE')
    process = subprocess.Popen([node, str(ROOT/'scripts/service_render_v3_worker.mjs')], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        start_new_session=os.name != 'nt')
    try:
        stdout, _ = process.communicate(json.dumps({'pages': pages}).encode(), timeout=timeout)
        result = json.loads(stdout)
        if process.returncode or result.get('error'):
            code = result.get('error')
            failure = RenderFailure(code if code in {'RENDER_LAYOUT_OVERFLOW', 'RENDER_FONT_UNAVAILABLE',
                                                'RENDER_UNSUPPORTED_GLYPH'} else 'RENDER_FAILED')
            failure.measurement = result.get('measurement')
            raise failure
        rows = result['results']
        if [r['template_id'] for r in rows] != ids:
            raise RenderFailure('RENDER_INVALID_RESULT')
        snapshot = sha256(json.dumps(asdict(data), ensure_ascii=False, sort_keys=True).encode()+photo).hexdigest()
        for row in rows:
            row['png'] = opaque_png(base64.b64decode(row['png'], validate=True))
            attach_contrast_evidence(row)
            row.pop('background_png', None)
            candidate_id, asset_id = uuid4().hex, uuid4().hex
            row.update(candidate_id=candidate_id, asset_id=asset_id, revision=1,
                       strategy='price', template_version=VERSION, input_snapshot=snapshot,
                       png_sha256=sha256(row['png']).hexdigest())
            row['diagnostics'] = measured_diagnostics(candidate_id, asset_id, 'price', row['measurement'], row['png_sha256'])
        return rows
    except subprocess.TimeoutExpired:
        raise RenderFailure('RENDER_TIMEOUT') from None
    except RenderFailure:
        raise
    except Exception:
        raise RenderFailure('RENDER_FAILED') from None
    finally:
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
