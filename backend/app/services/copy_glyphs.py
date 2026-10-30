"""No normalization: check actual bundled font coverage and disallow emoji sequences."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import unicodedata
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parents[3]/'templates/fonts/NotoSansKR-Regular.otf'
FONT_HASH = '69975a0ac8472717870aefeab0a4d52739308d90856b9955313b2ad5e0148d68'
POLICY_VERSION = 'noto-kr-2.004-text-v1'

@lru_cache(maxsize=1)
def supported_codepoints():
    if sha256(FONT.read_bytes()).hexdigest() != FONT_HASH:
        raise ValueError('Bundled font checksum mismatch')
    with TTFont(FONT) as font:
        return frozenset(font.getBestCmap())

def font_text_supported(text):
    return all(ord(c) in supported_codepoints() for c in text)

def supported_text(text):
    points = supported_codepoints()
    return all(ord(c) in points and unicodedata.category(c) != 'Cf'
        and not (0xFE00 <= ord(c) <= 0xFE0F or 0xE0100 <= ord(c) <= 0xE01EF)
        and ord(c) != 0x20E3
        # Includes monochrome emoji/decorative pictographs present in the font.
        and not (0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF)
        for c in text)
