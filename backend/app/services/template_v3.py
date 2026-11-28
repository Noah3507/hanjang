"""Opt-in local template renderer. Does not replace the four-strategy API."""
from dataclasses import dataclass, asdict, field, fields
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import base64
import json
import os
import shutil
import subprocess
from uuid import uuid4
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageOps

from app.services.render_execution import ROOT, FONT_HASH, RenderFailure, opaque_png, rgb
from app.services.diagnostics_evidence import attach_contrast_evidence
from app.services.diagnostics_engine import analyze
from app.services.design_style_context import StyleBundle

VERSION = 'ad-templates-v3-alpha-quality-3'
BOLD_HASH = '5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda'
NAMES = {'emotional': ('gallery', 'fade', 'editorial', 'door'),
         'price': ('circle', 'split', 'big-number', 'stamp'),
         'brand': ('wordmark', 'emblem', 'pattern', 'korean-wordmark'),
         'visual': ('full-bleed', 'polaroid', 'cinema', 'film')}
REGISTRY = {f'{strategy}_{letter}': {'strategy': strategy, 'variant': letter,
             'name': name, 'implemented': True}
            for strategy, names in NAMES.items() for letter, name in zip('abcd', names)}


def template_fingerprint():
    folder=ROOT/'templates/v3'
    paths=sorted(folder.glob('*.html'))+[folder/n for n in ('price.css','collection.css','quality.css')]
    signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in paths)
    return _template_fingerprint(signature)


@lru_cache(maxsize=8)
def _template_fingerprint(signature):
    digest=sha256()
    for name,_,_ in signature:
        path=Path(name);digest.update(path.name.encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def measured_diagnostics(candidate_id, asset_id, strategy, measurement, png_hash, *, template_id=None):
    """Adapt Chromium evidence to the existing renderer/diagnostics boundary."""
    measured_id=measurement.get('template_id')
    if template_id is not None:
        if template_id not in REGISTRY or REGISTRY[template_id]['strategy']!=strategy:
            raise ValueError('Invalid diagnostic template identity')
        if measured_id is not None and measured_id!=template_id:
            raise ValueError('Diagnostic template mismatch')
    elif measured_id in REGISTRY and REGISTRY[measured_id]['strategy']==strategy:
        template_id=measured_id
    boxes = []
    for text in measurement['text']:
        box = dict(text)
        box['foreground'] = rgb(box['foreground'])
        box['background'] = None if box['background'].endswith(', 0)') else rgb(box['background'])
        boxes.append(box)
    candidate = {'candidate_id': candidate_id, 'strategy': strategy, 'png': {'asset_id': asset_id},
                 'renderer': {'text_boxes': boxes, 'product_bbox': measurement['product']}}
    result=analyze(candidate, measurement, png_hash,template_id=template_id)
    from app.services.product_diagnostics import image_rules
    result.rules.extend(image_rules(measurement))
    coverage=[r.coverage for r in result.rules]
    result.coverage='complete' if all(v=='complete' for v in coverage) else 'unavailable' if all(v=='unavailable' for v in coverage) else 'partial'
    return result.model_dump(mode='json')


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
    style_context: StyleBundle | None = field(default=None, kw_only=True)

    def text_values(self):
        return {f.name:getattr(self,f.name) for f in fields(self) if f.name != 'style_context'}

    def validate(self):
        for name, value in self.text_values().items():
            if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
                raise RenderFailure('RENDER_INVALID_INPUT')
        if any(not getattr(self, k).strip() for k in ('store_name', 'product_name', 'headline')):
            raise RenderFailure('RENDER_INVALID_INPUT')
        from app.services.template_v3_claims import validate_promotion
        validate_promotion(self)


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
    from app.services.render_fonts import load_fonts, font_identity
    template_css = ''.join((ROOT/'templates/v3'/name).read_text(encoding='utf-8')
                           for name in ('price.css','collection.css','quality.css'))
    # Embed only requested families (plus the existing fallback). Every asset is
    # still integrity checked; inactive 24MB serif bytes need not inflate pages.
    families = {'HanjangNoto'} | {f for f in ('Noto Serif KR','Pretendard') if f in template_css}
    faces, _ = load_fonts(''.join(data.text_values().values()), families)
    font_fingerprint = font_identity()
    from app.services.product_geometry import prepare_product
    prepared,photo_info=prepare_product(photo)
    transparent=photo_info['transparent'];photo_fit='contain'
    uri = 'data:image/png;base64,' + base64.b64encode(prepared).decode()
    env = Environment(loader=FileSystemLoader(ROOT/'templates/v3'),
                      autoescape=select_autoescape(['html']), undefined=StrictUndefined)
    css = template_css + faces
    pages = [{'template_id': t, 'html': env.get_template(t+'.html').render(
        css=css + (data.style_context.page(t).css() if data.style_context else ''),
        data=data, photo=uri, photo_fit=photo_fit, transparent=transparent, template_id=t)} for t in ids]
    node = shutil.which('node')
    if not node:
        raise RenderFailure('RENDER_UNAVAILABLE')
    process = subprocess.Popen([node, str(ROOT/'scripts/service_render_v3_worker.mjs')], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        start_new_session=os.name != 'nt')
    try:
        stdout, _ = process.communicate(json.dumps({'pages': pages,'photo_info':photo_info}).encode(), timeout=timeout)
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
        snapshot = sha256(json.dumps({'data':asdict(data),'font_fingerprint':font_fingerprint,'template_source':template_fingerprint()}, ensure_ascii=False, sort_keys=True).encode()+photo).hexdigest()
        for row in rows:
            if row['measurement'].get('template_id')!=row['template_id']:
                raise RenderFailure('RENDER_INVALID_RESULT')
            row['png'] = opaque_png(base64.b64decode(row['png'], validate=True))
            attach_contrast_evidence(row)
            row.pop('background_png', None)
            candidate_id, asset_id = uuid4().hex, uuid4().hex
            row.update(candidate_id=candidate_id, asset_id=asset_id, revision=1,
                       strategy=REGISTRY[row['template_id']]['strategy'], template_version=VERSION, input_snapshot=snapshot,
                       png_sha256=sha256(row['png']).hexdigest())
            row['font_fingerprint'] = font_fingerprint
            row['style_snapshot'] = data.style_context.snapshot([row['template_id']]) if data.style_context else {}
            row['diagnostics'] = measured_diagnostics(candidate_id, asset_id, row['strategy'], row['measurement'], row['png_sha256'],template_id=row['template_id'])
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
