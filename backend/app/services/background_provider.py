"""Explicit text-only background experiment. No photo/fact input or automatic retry."""
import base64
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import uuid

from PIL import Image

MODEL = 'gpt-image-2.6-flare'
VERSION = 'empty-backdrop-v1'
RESERVATION = .25
MAX_ATTEMPTS = 16
MAX_COST_USD = 5
THEMES = {
    'noodle-editorial': 'Warm refined Chinese restaurant editorial mood, ivory plaster and softly woven neutral linen textures at the perimeter. Quiet warm ivory central surface and pale warm sand bottom area.',
    'noodle-dark': 'Premium contemporary Chinese restaurant mood, dark walnut tabletop photographed directly overhead, rich near-black warm brown, very restrained amber directional light. No red neon, no symbols.',
    'coffee-natural': 'Premium cafe natural morning light, pale travertine tabletop, soft warm shadows and sunlit texture at the far edge. Warm peach cream and muted tan, uncluttered editorial elegance.',
    'coffee-dark': 'Luxury minimal coffee-category studio campaign background, deep warm espresso-brown matte surface, subtle soft warm spotlight in center, quiet near-black brown surroundings. No coffee beans or equipment.',
}


def background_prompt(theme):
    if theme not in THEMES:
        raise ValueError('Unsupported server-owned theme')
    return '''Create an EMPTY photographic advertising BACKDROP, portrait 2:3. This is a background plate for later LOCAL compositing; do not create an advertisement or the featured product.
Camera is perfectly overhead, flat lay, no horizon, no perspective wall, no pedestal.
Reserve the central region x=12%-88%, y=14%-70% as a clean uninterrupted surface for a separately photographed real item. Lighting must be broad and soft, not a drawn object-shaped shadow. Do not draw any placeholder shapes or boxes.
Reserve y=0%-12% and y=73%-100% as quiet, low-detail uniform tonal areas for LOCAL text overlay. Keep any texture subtle and mostly toward the outer perimeter. No text, letters, symbols, watermark, logo, labels, prices or borders anywhere.
ABSOLUTELY EMPTY: no food, noodles, ingredients, beans, cups, mugs, bowls, plates, bottles, packages, utensils, chopsticks, hands, people, plants, menu or product. Nothing that resembles a duplicate product. Only surface, light, restrained texture and atmosphere.
''' + THEMES[theme]


class BackgroundBudget:
    def __init__(self, path):
        self.path = Path(path)

    def update(self, action):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.lock')
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'kind': 'image-background', 'calls': []}
            if not isinstance(data, dict) or data.get('kind') != 'image-background' or not isinstance(data.get('calls'), list): raise ValueError('Invalid image ledger')
            for c in data['calls']:
                value = c['cost_ceiling_usd']
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0: raise ValueError('Invalid image cost')
            result = action(data)
            temp = self.path.with_suffix('.tmp');temp.write_text(json.dumps(data, indent=2), encoding='utf-8');temp.replace(self.path)
            return result
        finally:
            lock.unlink()

    def reserve(self, key):
        def action(data):
            if any(c.get('reservation_exceeded') for c in data['calls']):
                raise ValueError('Image cost reservation exceeded; experiment stopped')
            if len(data['calls']) >= MAX_ATTEMPTS or sum(c['cost_ceiling_usd'] for c in data['calls'])+RESERVATION > MAX_COST_USD:
                raise ValueError('Image budget exhausted')
            if any(c['request_key'] == key for c in data['calls']):raise ValueError('Duplicate generation request; no automatic retry')
            ident = uuid.uuid4().hex
            data['calls'].append({'id': ident, 'request_key': key, 'state': 'reserved', 'model': MODEL,
                                  'cost_ceiling_usd': RESERVATION, 'usage_known': False})
            return ident
        return self.update(action)

    def record(self, ident, **values):
        self.update(lambda data: next(c for c in data['calls'] if c['id'] == ident).update(values))


@dataclass(frozen=True)
class BackgroundResult:
    png: bytes
    sha256: str
    call_id: str
    cost_usd: float | None


class OpenAIBackgroundProvider:
    """Not wired into ordinary ad generation. Explicit paid gate required."""
    def __init__(self, client, ledger, *, allow_paid=False):
        self.client, self.budget, self.allow_paid = client, BackgroundBudget(ledger), allow_paid

    def generate(self, theme, request_key, capture):
        if self.allow_paid is not True:raise ValueError('Paid image generation disabled')
        if getattr(self.client, 'max_retries', None) != 0:raise ValueError('Image retries must be zero')
        prompt = background_prompt(theme)
        if len(prompt.encode('utf-8')) > 3000:raise ValueError('Background prompt limit')
        args = dict(model=MODEL, prompt=prompt, n=1, size='1024x1536', quality='medium',
                    output_format='png', background='opaque', moderation='auto', extra_body={'complexity':'low'})
        # Only whitelisted server-owned text reaches this endpoint. No image,
        # URL, product fact or arbitrary user string is accepted by this method.
        capture(args, None)
        call = self.budget.reserve(request_key)
        self.budget.record(call, state='dispatched', prompt_version=VERSION,
                           prompt_sha256=sha256(prompt.encode('utf-8')).hexdigest())
        cost = None
        try:
            response = self.client.images.generate(**args)
            usage = response.usage
            if usage is not None:
                details = usage.input_tokens_details
                text = details.text_tokens; image = details.image_tokens; output = usage.output_tokens
                if any(type(x) is not int or x < 0 for x in (text, image, output)) or image != 0:
                    raise ValueError('Unexpected image input or usage')
                cost = (text*5+output*30)/1e6
                self.budget.record(call, usage_known=True, cost_ceiling_usd=cost,
                    text_input_tokens=text, image_input_tokens=image, output_tokens=output, state='completed',
                    reservation_exceeded=cost > RESERVATION)
                if cost > RESERVATION:raise ValueError('Actual image cost exceeded reservation; stop experiment')
            else:
                self.budget.record(call, state='usage-unknown')
            # Settle known cost even if local response persistence fails.
            capture(args, response)
            if len(response.data or []) != 1:raise ValueError('Expected one image')
            png = base64.b64decode(response.data[0].b64_json, validate=True)
            with Image.open(BytesIO(png)) as im:
                if im.format != 'PNG' or im.size != (1024,1536) or im.mode not in ('RGB','RGBA'):raise ValueError('Unexpected background image')
                im.load()
            return BackgroundResult(png,sha256(png).hexdigest(),call,cost)
        except Exception as error:
            self.budget.record(call, state='failed', error_type=type(error).__name__,
                               http_status=getattr(error,'status_code',None))
            raise RuntimeError('Background generation failed; no retry; cost recorded conservatively') from None
