"""Generate source-authorized procedural complex imagery and all 16 v3 previews.

No external images, APIs, model downloads, user assets or existing outputs touched.
"""
import argparse
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import random
import sys
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.services.template_v3 import TemplateInput,render_templates,NAMES,VERSION
from app.services.render_execution import RenderFailure


def complex_photo(size=(900,900),transparent=False,dark=False):
    """Original procedural scene with texture, gradients, glass-like highlights/shadow.

    Synthetic, NOT a licensed photograph nor evidence of real-photo quality.
    """
    random.seed(15)
    w,h=size
    image=Image.new('RGBA',size,(0,0,0,0) if transparent else '#d4d0c8')
    if not transparent:
        draw=ImageDraw.Draw(image)
        for y in range(h):
            v=175+int(60*y/h);draw.line((0,y,w,y),fill=(v,min(255,v+7),min(255,v+4),255))
        for _ in range(12000):
            x,y=random.randrange(w),random.randrange(h);v=random.randrange(130,235)
            draw.point((x,y),fill=(v,v,min(255,v+15),255))
    shadow=Image.new('RGBA',size);d=ImageDraw.Draw(shadow)
    d.ellipse((w*.2,h*.78,w*.85,h*.9),fill=(20,20,20,100));image=Image.alpha_composite(image,shadow.filter(ImageFilter.GaussianBlur(18)))
    d=ImageDraw.Draw(image);ink='#242a2a' if dark else '#f1f0e8'
    d.rounded_rectangle((w*.32,h*.2,w*.68,h*.83),radius=int(w*.055),fill=ink,outline='#656f69',width=4)
    d.rounded_rectangle((w*.39,h*.09,w*.61,h*.24),radius=12,fill='#6e7c74')
    d.rectangle((w*.37,h*.43,w*.63,h*.66),fill='#c7a978')
    d.line((w*.36,h*.28,w*.36,h*.76),fill='#ffffff',width=6)
    d.ellipse((w*.47,h*.49,w*.54,h*.57),fill='#394d36')
    stream=BytesIO();image.save(stream,'PNG');return stream.getvalue()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve()
    if out.exists() or out==ROOT or ROOT in out.parents:p.error('Use a new directory outside the repository')
    out.mkdir(parents=True)
    cases=[('representative',(900,900),False,False,False,False),
           ('tall-transparent',(480,1000),True,True,True,False),
           ('wide-private-price',(1100,550),False,False,False,True)]
    summary=[]
    for name,size,alpha,dark,long,private in cases:
        folder=out/name;folder.mkdir();photo=complex_photo(size,alpha,dark);(folder/'source.png').write_bytes(photo)
        data=TemplateInput('한장 상점','데일리 로션' if not long else '매일 사용하는 데일리 보습 로션',
            '가격 비공개' if private else '10,500원','일상에 더하는 작은 여유',
            '상품 구성과 가격을 확인하세요.' if not long else '매일 사용하는 상품입니다. 구성과 가격을 확인하고 나에게 맞는 상품을 선택하세요.',
            '상품 보기')
        if long:data=replace(data,original_price='15,000원',discount_text='30%',promotion_text='테스트 행사',period_text='2026.11.16–2026.11.20')
        rows=[]
        for strategy in NAMES:
            try:
                result=render_templates(data,photo,[f'{strategy}_{c}' for c in 'abcd'])
                for row in result:
                    f=folder/(row['template_id']+'.png');f.write_bytes(row.pop('png'));row['file']=f.name;rows.append(row)
                print(name,strategy,'OK',flush=True)
            except RenderFailure as e:
                (folder/(strategy+'-failure.json')).write_text(json.dumps({'code':e.code,'measurement':getattr(e,'measurement',None)},ensure_ascii=False,indent=2),encoding='utf-8')
                raise
        metadata={'input':data.__dict__,'source_sha256':sha256(photo).hexdigest(),'asset_rights':'Original procedural synthetic scene, not a real photograph.',
                  'version':VERSION,'results':rows}
        (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        summary.append({'case':name,'png_count':len(rows)})
    links=''
    for strategy in NAMES:
        for c in 'abcd':
            tid=f'{strategy}_{c}';links+=f'<figure><img src="representative/{tid}.png"><figcaption>{tid} · {NAMES[strategy][ord(c)-97]}</figcaption></figure>'
    (out/'gallery.html').write_text('<!doctype html><meta charset="UTF-8"><title>Hanjang Phase 15 — 16 designs</title><style>body{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;background:#ddd;font-family:sans-serif}figure{margin:0}img{width:100%;height:auto;aspect-ratio:4/5}figcaption{padding:8px}@media(max-width:600px){body{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'+links,encoding='utf-8')
    sheet=Image.new('RGB',(1080,4*355),'#ddd')
    for i,(s,c) in enumerate((s,c) for s in NAMES for c in 'abcd'):
        im=Image.open(out/'representative'/f'{s}_{c}.png');im.thumbnail((270,337));sheet.paste(im,((i%4)*270,(i//4)*355))
    sheet.save(out/'gallery.png')
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__=='__main__':main()
