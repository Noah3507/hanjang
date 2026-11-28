"""Reviewed LOCAL plates only. No generator/client/facts or public API input."""
import base64
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re

from PIL import Image

VERSION = 'background-texture-safe-v1'
PROMPT_VERSION = 'empty-layout-backdrop-v1'
SUPPORTED = frozenset({'visual_a', 'visual_d', 'emotional_a'})


@dataclass(frozen=True)
class BackgroundPage:
    template_id: str
    asset_id: str
    sha256: str
    model: str
    prompt_version: str
    png_base64: str
    policy: str = 'directed'
    source: str = 'reviewed-local-plate'

    def snapshot(self):
        return {k: v for k, v in self.__dict__.items() if k != 'png_base64'}


@dataclass(frozen=True)
class BackgroundContext:
    owner: str
    job: str
    expires_at: str
    pages: tuple[BackgroundPage, ...]

    def snapshot(self):
        return {'version': VERSION, 'owner': self.owner, 'job': self.job,
                'expires_at': self.expires_at, 'pages': [p.snapshot() for p in self.pages]}

    def selections(self):
        return {p.template_id: p.asset_id for p in self.pages}

    def worker_pages(self, ids):
        return {p.template_id: {**p.snapshot(), 'png_base64': p.png_base64, 'version': VERSION}
                for p in self.pages if p.template_id in ids}


class BackgroundLibrary:
    """Server-injected manifest of reviewed, fact-free background files.

    Never discover assets or trust request paths. Each resolution verifies bytes;
    the immutable resolved context survives a missing source file until job TTL.
    """
    def __init__(self, root, manifest):
        self.root = Path(root).resolve()
        self.manifest = json.loads(json.dumps(manifest))

    def context(self, owner, job, expires_at, selections):
        if not selections:
            return None
        if len(selections) > len(SUPPORTED) or not set(selections) <= SUPPORTED:
            raise ValueError('Background template not supported')
        pages = []
        for tid, asset_id in sorted(selections.items()):
            item = self.manifest.get(asset_id)
            if not item or item.get('reviewed') is not True or tid not in item.get('templates', []):
                raise ValueError('Background asset unavailable or incompatible')
            relative = Path(item['file'])
            candidate = self.root/relative
            path = candidate.resolve()
            if relative.is_absolute() or not path.is_relative_to(self.root) or candidate.is_symlink():
                raise ValueError('Background path invalid')
            if path.stat().st_size > 8_000_000:
                raise ValueError('Background too large')
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Background integrity failure')
            with Image.open(BytesIO(raw)) as image:
                if image.format != 'PNG' or image.mode != 'RGB' or image.width*image.height > 4_000_000:
                    raise ValueError('Background image invalid')
                image.load()
            if not isinstance(item['model'], str) or not isinstance(item['prompt_version'], str):
                raise ValueError('Background provenance missing')
            pages.append(BackgroundPage(tid, asset_id, item['sha256'], item['model'], item['prompt_version'],
                                        base64.b64encode(raw).decode(), source=item.get('source','reviewed-local-plate')))
        return BackgroundContext(owner, job, expires_at.isoformat(), tuple(pages))


def prompt_plan(category, strategy, goal, measurement, palette, *, category_confirmed=False):
    """Offline request plan. All language is server-owned; geometry is local.

    Does not call the image provider or reserve costs. Category hints remain
    explicitly uncertain. Facts, source photos and arbitrary strings aren't inputs.
    """
    if category not in {'noodles', 'coffee'} or strategy not in {'visual', 'emotional'}:
        raise ValueError('Unsupported background direction')
    if goal not in {'menu_promotion', 'store_visit', 'order'}:
        raise ValueError('Invalid goal')
    if not 1 <= len(palette) <= 5 or any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', p) for p in palette):
        raise ValueError('Invalid palette')
    def box(value):
        values = [value[k] for k in ('x', 'y', 'width', 'height')]
        if any(type(v) not in (int, float) or not 0 <= v <= 1350 for v in values):
            raise ValueError('Invalid geometry')
        if values[0]+values[2] > 1081 or values[1]+values[3] > 1351:
            raise ValueError('Invalid geometry')
        if values[2]<=0 or values[3]<=0:
            raise ValueError('Empty geometry')
        return dict(zip(('x', 'y', 'width', 'height'), (round(v, 2) for v in values)))
    product = box(measurement['product'])
    texts = [box(t) for t in measurement['text']]
    if len(texts) > 20:
        raise ValueError('Too many text regions')
    spec = {'canvas': [1080, 1350], 'category': category, 'category_confirmed': category_confirmed is True,
            'strategy': strategy, 'goal': goal, 'palette': palette, 'empty_product_region': product,
            'quiet_text_regions': texts, 'contact_y': round(product['y']+product['height'], 2),
            'camera': 'overhead flat lay', 'light': 'broad soft upper-left, reviewed assumption',
            'material': 'subtle warm stone' if category == 'coffee' else 'subtle warm neutral tabletop'}
    # The existing image endpoint size is 1024x1536, not the final 4:5 PNG.
    # Map reservations through the same cover/alignment as the compositor.
    scale=1080/1024
    offset=max(0,min(1536*scale-1350,1536*scale*.42-(product['y']+product['height']/2)))
    def source_box(rect):
        return {'x':round(rect['x']/scale,2),'y':round((rect['y']+offset)/scale,2),
                'width':round(rect['width']/scale,2),'height':round(rect['height']/scale,2)}
    spec.update(generation_canvas=[1024,1536],source_product_region=source_box(product),
                source_text_regions=[source_box(t) for t in texts],ground_plane='overhead surface, not a pedestal')
    return {'version': PROMPT_VERSION, 'spec': spec, 'prompt':
            'Create only an empty commercial photographic BACKGROUND plate. No advertisement or product. '
            'Keep the given product region empty and the text regions quiet. No horizon/pedestal. '
            'Do not draw a product-shaped shadow: contact shadow is a separate local responsibility. '
            'No food, cup, bowl, plate, utensil, package, logo, watermark, text, letters or numbers. '
            'Do not infer ingredients/origin or brand facts. Geometry and colors below are layout constraints, '
            'not text to print. Use source regions on the generation canvas; canvas regions describe the final crop. '
            + json.dumps(spec, ensure_ascii=True, sort_keys=True,separators=(',',':'))}
