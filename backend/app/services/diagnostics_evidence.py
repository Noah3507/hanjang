"""Conservative contrast evidence from a paired Chromium background capture."""
import base64
from hashlib import sha256
from io import BytesIO
import math
import re
from PIL import Image

EVIDENCE_VERSION='chromium-background-pixels-v1'

def attach_contrast_evidence(result):
    """Never guess a background from CSS alone or sample antialiased glyphs."""
    background=result.pop('background_png',None)
    image=None
    if background:
        try:
            image=Image.open(BytesIO(base64.b64decode(background,validate=True)))
            image.load()
            if image.size!=(1080,1350):image=None
            elif image.mode!='RGB':image=image.convert('RGBA')
        except Exception:image=None
    for text in result['measurement'].get('text',[]):
        evidence={'version':EVIDENCE_VERSION,'status':'unavailable','reason':'검증된 배경 픽셀 또는 합성 근거가 없습니다.',
                  'png_sha256':sha256(result['png']).hexdigest(),'foreground_rgb':None,'background_rgb':None}
        text['contrast_evidence']=evidence
        if not text.get('contrast_eligible') or image is None:continue
        match=re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)',text.get('foreground',''))
        if not match:continue
        colors=[]
        try:
            rects=text.get('glyph_rects')
            if not isinstance(rects,list) or not rects:continue
            for rect in rects:
                x,y,w,h=(rect[k] for k in ('x','y','width','height'))
                if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (x,y,w,h)):raise ValueError()
                if w<=0 or h<=0 or x<0 or y<0 or x+w>1080 or y+h>1350:raise ValueError()
                crop=image.crop((math.floor(x),math.floor(y),math.ceil(x+w),math.ceil(y+h)))
                extrema=crop.getextrema()
                if any(a!=b for a,b in extrema) or len(extrema)==4 and extrema[3]!=(255,255):raise ValueError()
                colors.append(tuple(v[0] for v in extrema[:3]))
            if len(set(colors))!=1:raise ValueError()
            fg=[int(n) for n in match.groups()]
            if any(n>255 for n in fg):raise ValueError()
            evidence.update(status='verified',reason=None,foreground_rgb=fg,background_rgb=list(colors[0]))
        except Exception:
            evidence['reason']='배경 픽셀이 균일하지 않거나 검증 가능한 영역이 아닙니다.'
    if image is not None:image.close()
