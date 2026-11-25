"""Offline, checksum-pinned v3 font assets. No OS fonts or runtime downloads."""
import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from app.services.render_execution import ROOT, RenderFailure

ASSETS = ROOT / 'backend/assets/fonts'


def load_fonts(text='', families=None):
    """Validate every declared face before rendering, even if CSS does not use it.

    Missing/corrupt primary assets fail closed. Valid primary faces may fall back
    per glyph to the existing HanjangNoto; its coverage remains the input gate.
    """
    try:
        manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
        faces = []
        for entry in manifest['faces']:
            path = ROOT / entry['path']
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('font integrity')
            if text and entry['family'] == 'HanjangNoto':
                with TTFont(BytesIO(raw)) as font:
                    if any(ord(c) not in font.getBestCmap() for c in text):
                        raise RenderFailure('RENDER_UNSUPPORTED_GLYPH')
            if families is not None and entry['family'] not in families:
                continue
            uri = base64.b64encode(raw).decode('ascii')
            faces.append(f"@font-face{{font-family:'{entry['family']}';src:url(data:{entry['mime']};base64,{uri});font-weight:{entry['weight']};font-style:normal;font-display:block}}")
        fingerprint = sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return ''.join(faces), fingerprint
    except RenderFailure:
        raise
    except Exception:
        raise RenderFailure('RENDER_FONT_UNAVAILABLE') from None


def font_identity():
    # Validate actual bytes, not only a manifest mtime; a missing/replaced asset
    # must invalidate existing sets before ranking/edit/download can reuse them.
    try:
        raw = (ASSETS / 'manifest.json').read_bytes()
        manifest = json.loads(raw)
        hashes = [sha256((ROOT / f['path']).read_bytes()).hexdigest() for f in manifest['faces']]
        return sha256(raw + json.dumps(hashes).encode()).hexdigest()
    except (OSError, ValueError, KeyError):
        return 'font-assets-unavailable'
