"""Offline, checksum-pinned v3 font assets. No OS fonts or runtime downloads."""
import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from collections import OrderedDict
from threading import RLock

from fontTools import subset as font_subset
from fontTools import __version__ as FONTTOOLS_VERSION
from fontTools.ttLib import TTFont
from app.services.render_execution import ROOT, RenderFailure

ASSETS = ROOT / 'backend/assets/fonts'
# Characters always kept, so punctuation the renderer or browser adds still uses the face.
SUBSET_BASE = ''.join(chr(c) for c in range(0x20, 0x7f)) + '₩·…“”‘’〜'
SUBSET_VERSION = 'subset-v1-layout-all-hinted-renamed-fonttools-' + FONTTOOLS_VERSION
CACHE_MAX_ENTRIES = 128
CACHE_MAX_BYTES = 16 * 1024 * 1024
CACHE_MAX_ENTRY_BYTES = 1024 * 1024
CACHE_MAX_CHARACTERS = 21000
_cache = OrderedDict()
_cache_bytes = 0
_cache_lock = RLock()


def _subset_name(digest):
    return 'HanjangSubset' + digest[:12]


def _subset(raw: bytes, digest: str, characters: str) -> bytes:
    """The verified face cut down to the ad's characters (weight axis and layout features kept).
    Full faces become small per-text faces, keeping pages compact. Keyed by the
    verified digest, canonical characters and option version. Use the verified
    bytes themselves, never reopen a mutable path after validation."""
    global _cache_bytes
    key = (digest, characters, SUBSET_VERSION)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    with TTFont(BytesIO(raw), recalcTimestamp=False) as font:
        options = font_subset.Options()
        options.layout_features = ['*']
        options.name_IDs = ['*']
        options.notdef_outline = True
        options.hinting = True  # Keep full-face rasterization, not only metrics.
        subsetter = font_subset.Subsetter(options)
        subsetter.populate(text=characters)
        subsetter.subset(font)
        # Subsetting creates a modified font. Preserve copyright/license names,
        # but do not ship Pretendard's Reserved Font Name as a primary font name.
        name = _subset_name(digest)
        instance_names = {i.postscriptNameID for i in font['fvar'].instances
                          if i.postscriptNameID != 0xFFFF} if 'fvar' in font else set()
        for record in font['name'].names:
            if record.nameID in {1,3,4,6,16,18,20,21,22,25} | instance_names:
                value = name + (f'-I{record.nameID}' if record.nameID in instance_names else '')
                record.string = value.encode(record.getEncoding())
        if 'CFF ' in font:
            cff=font['CFF '].cff
            cff.fontNames=[name]
            cff.topDictIndex[0].FamilyName=name
            cff.topDictIndex[0].FullName=name
        buffer = BytesIO()
        font.save(buffer)
        result=buffer.getvalue()
    with _cache_lock:
        if key not in _cache and len(result)<=min(CACHE_MAX_ENTRY_BYTES,CACHE_MAX_BYTES) and len(characters)<=CACHE_MAX_CHARACTERS:
            while _cache and (len(_cache)>=CACHE_MAX_ENTRIES or _cache_bytes+len(result)>CACHE_MAX_BYTES):
                _,evicted=_cache.popitem(last=False)
                _cache_bytes-=len(evicted)
            _cache[key]=result
            _cache_bytes+=len(result)
    return result


def load_fonts(text='', families=None):
    """Validate every declared face before rendering, even if CSS does not use it.

    Missing/corrupt primary assets fail closed. Valid primary faces may fall back
    per glyph to the existing HanjangNoto; its coverage remains the input gate.
    """
    try:
        manifest = json.loads((ASSETS / 'manifest.json').read_text(encoding='utf-8'))
        faces = []
        characters = ''.join(sorted(set(text + SUBSET_BASE)))
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
            if text:
                raw = _subset(raw, entry['sha256'], characters)
            uri = base64.b64encode(raw).decode('ascii')
            faces.append(f"@font-face{{font-family:'{entry['family']}';src:url(data:{entry['mime']};base64,{uri});font-weight:{entry['weight']};font-style:normal;font-display:block}}")
        fingerprint = sha256((json.dumps(manifest, sort_keys=True)+SUBSET_VERSION).encode()).hexdigest()
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
        return sha256(raw + json.dumps(hashes).encode()+SUBSET_VERSION.encode()).hexdigest()
    except (OSError, ValueError, KeyError):
        return 'font-assets-unavailable'
