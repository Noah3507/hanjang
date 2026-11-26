"""Render-only photo selection. Never changes analysis selection or stored assets."""
from hashlib import sha256
from io import BytesIO
from PIL import Image, ImageOps
from app.services.uploads import UploadError

VERSION = 'original-rgb-white-v1'


def render_photo(uploads, owner, record, selected, draft, max_side=1600):
    original = draft.photo_mode == 'original'
    # Explicit cutout uses an already available processing asset. Keep the
    # analysis selection unchanged; never trigger processing on a mode switch.
    processed = getattr(getattr(record,'photo',None),'processed',None)
    chosen = processed or selected
    asset_id = record.upload.asset_id if original else chosen.asset_id
    raw, _ = uploads.read_asset(owner, asset_id)
    expected = record.upload.sha256 if original else chosen.sha256
    if sha256(raw).hexdigest() != expected:
        raise UploadError(409, 'RENDER_PHOTO_CHANGED', '사진 파일이 변경됐습니다. 다시 확인해 주세요.')
    if not original:
        return raw
    try:
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert('RGBA')
        # Composite before discarding alpha: hidden RGB must never become spots.
        background = Image.new('RGBA', image.size, (255,255,255,255))
        image = Image.alpha_composite(background, image).convert('RGB')
        image.thumbnail((max_side,max_side), Image.Resampling.LANCZOS)
        output=BytesIO();image.save(output,format='PNG')
        return output.getvalue()
    except Exception:
        raise UploadError(422,'RENDER_PHOTO_INVALID','원본 사진을 읽을 수 없습니다.') from None
