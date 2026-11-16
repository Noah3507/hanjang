"""Offline reproducible v2/v3 comparison using original synthetic test artwork.

All files go to a NEW directory outside the repository. No API/provider/store.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from PIL import Image, ImageDraw
from app.schemas.upload import InputDraft
from app.services.render_execution import RenderExecution, VERSION as V2, ORDERS
from app.services.template_v3 import TemplateInput, render_templates, measured_diagnostics, VERSION as V3


def sample(kind, size, transparent, dark):
    """Code-authored shapes, not a photograph or a real brand/product."""
    im = Image.new('RGBA', size, (0, 0, 0, 0) if transparent else '#e8e8df')
    d = ImageDraw.Draw(im); w, h = size; ink = '#252529' if dark else '#fafafa'
    if kind == 'bottle':
        d.rounded_rectangle((w*.3,h*.15,w*.7,h*.9),radius=30,fill=ink,outline='#555',width=4)
        d.rectangle((w*.35,h*.08,w*.65,h*.2),fill='#888')
        d.rectangle((w*.34,h*.44,w*.66,h*.65),fill='#d6b277')
    elif kind == 'shirt':
        d.polygon([(w*.32,h*.2),(w*.15,h*.26),(w*.05,h*.5),(w*.25,h*.57),(w*.29,h*.85),
                   (w*.71,h*.85),(w*.75,h*.57),(w*.95,h*.5),(w*.85,h*.26),(w*.68,h*.2)],fill=ink,outline='#777')
    else:
        d.rounded_rectangle((w*.15,h*.2,w*.85,h*.8),radius=40,fill=ink,outline='#777',width=5)
        d.ellipse((w*.37,h*.32,w*.63,h*.68),fill='#bf945b',outline='#555',width=5)
    out = BytesIO(); im.save(out,'PNG'); return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); out = args.output.resolve()
    if out == ROOT or ROOT in out.parents or out.exists():
        parser.error('Use a new output directory outside the repository')
    out.mkdir(parents=True)
    cases = [('bottle', (400,800), True, False, '보습 크림', False),
             ('shirt', (900,500), False, True, '데일리 셔츠', True),
             ('speaker', (700,500), False, True, '휴대용 스피커', False),
             ('bottle', (400,900), True, True, '아침과 저녁에 사용하는 데일리 보습 로션', True),
             ('speaker', (900,400), True, False, '화이트 스피커', False)]
    report = {'v2_version':V2,'v3_version':V3,'asset_rights':'Original code-authored synthetic shapes; no real product photos.',
              'comparison':'v2 four strategies and v3 four price variants are separate evaluation sets.', 'cases':[]}
    for index,(kind,size,transparent,dark,name,promo) in enumerate(cases):
        folder = out/f'case-{index+1}';folder.mkdir()
        photo = sample(kind,size,transparent,dark); (folder/'source.png').write_bytes(photo)
        body = '상품 구성과 가격을 확인하세요.' if index != 3 else '매일 사용하는 상품입니다. 구성과 가격을 확인하고 나에게 맞는 상품을 선택하세요.'
        data = TemplateInput('한장 테스트 상점',name,'10,500원','일상에 더하는 선택',body,'상품 보기',
                             '10%' if promo else '', '11,700원' if promo else '', '테스트 행사' if promo else '',
                             '2026.11.16–11.20' if promo else '')
        draft = InputDraft.model_validate({'facts':{'store_name':data.store_name,'product_name':name,'price_text':data.price_text},'mood':'warm'})
        variants = SimpleNamespace(variants=[SimpleNamespace(strategy=s,ad_copy=SimpleNamespace(
            model_dump=lambda:{'headline':data.headline,'body':body,'cta':data.cta})) for s in ORDERS])
        rows = []
        for row in RenderExecution()(draft,variants,photo):
            path = folder/f'v2-{row["strategy"]}.png';path.write_bytes(row.pop('png'))
            row.update(file=path.name,template_version=V2,png_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            row['diagnostics']=measured_diagnostics('baseline-'+row['strategy'],'baseline',row['strategy'],row['measurement'],row['png_sha256'])
            rows.append(row)
        try:
            rendered = render_templates(data,photo)
        except Exception as error:
            (folder/'failure.json').write_text(json.dumps({'error':getattr(error,'code','REVIEW_FAILED'),
                'measurement':getattr(error,'measurement',None)},ensure_ascii=False,indent=2),encoding='utf-8')
            raise
        for row in rendered:
            path=folder/f'v3-{row["template_id"]}.png';path.write_bytes(row.pop('png'));row['file']=path.name;rows.append(row)
        entry={'input':data.__dict__,'source_sha256':hashlib.sha256(photo).hexdigest(),'size':size,
               'transparent':transparent,'dark':dark,'results':rows}
        (folder/'metadata.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf-8')
        report['cases'].append({'folder':folder.name,'png_count':len(rows)})
        print(f'{folder.name}: {len(rows)} PNG',flush=True)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    cards=[]
    for p in out.glob('case-*/v3-*.png'):
        im=Image.open(p);im.thumbnail((216,270));cards.append((p,im.copy()))
    gallery=Image.new('RGB',(864,300*len(cases)),'#ddd')
    for i,(p,im) in enumerate(cards):gallery.paste(im,((i%4)*216,(i//4)*300))
    gallery.save(out/'gallery.png')
    links=''.join(f'<figure><img src="{p.relative_to(out).as_posix()}" width="216"><figcaption>{p.parent.name} / {p.stem}</figcaption></figure>' for p,_ in cards)
    (out/'gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>v3 price review</title><style>body{display:grid;grid-template-columns:repeat(4,1fr);background:#ddd}figure{margin:12px}img{width:100%;max-width:320px}</style>'+links,encoding='utf-8')


if __name__ == '__main__':
    main()
