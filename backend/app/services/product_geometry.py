"""Read-only alpha geometry, not semantic segmentation or product recognition."""
from hashlib import sha256
from io import BytesIO
import math
from PIL import Image, ImageOps
from app.services.render_execution import RenderFailure

POLICY_VERSION = 'alpha-support-placement-v1'
ALPHA_THRESHOLD = 16
MAX_LOST_ALPHA_MASS = .002


def prepare_product(data):
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width*source.height>24_000_000:
                raise ValueError('image limit')
            original_size=source.size
            image=ImageOps.exif_transpose(source).convert('RGBA')
    except Exception:
        raise RenderFailure('RENDER_INVALID_IMAGE') from None
    oriented_size=image.size
    alpha=image.getchannel('A');transparent=alpha.getextrema()[0]<255
    loose=alpha.getbbox();mask=alpha.point(lambda value:255 if value>=ALPHA_THRESHOLD else 0)
    support=mask.getbbox() if transparent else None
    crop=(0,0,*image.size);lost=0.;warnings=[]
    if transparent and support:
        pad=max(2,math.ceil(max(support[2]-support[0],support[3]-support[1])*.02))
        proposed=(max(0,support[0]-pad),max(0,support[1]-pad),min(image.width,support[2]+pad),min(image.height,support[3]+pad))
        mass=lambda a:sum(i*n for i,n in enumerate(a.histogram()))
        total=mass(alpha)
        lost=(total-mass(alpha.crop(proposed)))/total if total else 0.
        if lost<=MAX_LOST_ALPHA_MASS:
            crop=proposed
        else:
            lost=0.;warnings.append('ALPHA_TRIM_UNCERTAIN_KEEP_FULL_IMAGE')
    elif transparent:
        warnings.append('ALPHA_SUBJECT_UNAVAILABLE')
    else:
        warnings.append('OPAQUE_PHOTO_SUBJECT_UNKNOWN')
    prepared=image.crop(crop)
    support_relative=([support[0]-crop[0],support[1]-crop[1],support[2]-crop[0],support[3]-crop[1]] if support else None)
    # Row extrema suffice for containment in a convex circle/ellipse; no contour
    # simplification can silently discard a disconnected object/accessory.
    rows=[]
    if support_relative:
        clipped=mask.crop(crop)
        for y in range(clipped.height):
            row=clipped.crop((0,y,clipped.width,y+1)).getbbox()
            if row:rows.append([y,row[0],row[2]])
    buffer=BytesIO();prepared.save(buffer,'PNG');png=buffer.getvalue()
    info={'version':POLICY_VERSION,'source_sha256':sha256(data).hexdigest(),
          'prepared_sha256':sha256(png).hexdigest(),'original_size':list(original_size),
          'oriented_size':list(oriented_size),'prepared_size':list(prepared.size),
          'transparent':transparent,'alpha_threshold':ALPHA_THRESHOLD,'alpha_bbox':list(loose) if loose else None,
          'support_bbox':list(support) if support else None,'crop_box':list(crop),
          'support_in_prepared':support_relative,'discarded_low_alpha_mass_ratio':lost,
          'subject_detection':'alpha-support' if support else 'unavailable',
          'warnings':warnings,'support_rows':rows}
    return png,info
