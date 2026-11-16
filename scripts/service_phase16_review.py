"""Local-only quality review. User images are read, never changed or committed."""
import argparse
from dataclasses import replace,asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import types
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.schemas.upload import InputDraft
from app.services.copy_validation import validate_copy
from app.services.template_v3 import render_templates,TemplateInput,NAMES
from app.services.render_execution import RenderFailure
from service_v3_gallery import complex_photo
from service_template_v3_review import sample


def baseline(root):
    """Read pinned Git objects, not a checkout/reset or user backup reapplication."""
    root=root.resolve();ref='f9c1deb';root.mkdir()
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'templates/v3','templates/fonts'],cwd=ROOT,text=True).splitlines()
    worker='scripts/service_render_v3_worker.mjs';paths.append(worker)
    hashes={}
    for name in paths:
        data=subprocess.check_output(['git','show',f'{ref}:{name}'],cwd=ROOT);target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        hashes[name]=sha256(data).hexdigest()
        if name==worker:
            data=data.replace(b"'../frontend/node_modules/playwright/index.mjs'",("'"+(ROOT/'frontend/node_modules/playwright/index.mjs').as_uri()+"'").encode())
            # Observe legacy painted bounds without modifying any DOM/style/PNG.
            probe="""measurement.legacy_image=await page.evaluate(()=>{const e=document.querySelector('.photo img'),s=getComputedStyle(e),r=e.getBoundingClientRect();const pl=parseFloat(s.paddingLeft),pr=parseFloat(s.paddingRight),pt=parseFloat(s.paddingTop),pb=parseFloat(s.paddingBottom),bl=parseFloat(s.borderLeftWidth),bt=parseFloat(s.borderTopWidth);const w=e.clientWidth-pl-pr,h=e.clientHeight-pt-pb,k=Math.min(w/e.naturalWidth,h/e.naturalHeight);return {natural_width:e.naturalWidth,natural_height:e.naturalHeight,padding:[pl,pt,pr,pb],object_fit:s.objectFit,painted_rect:{x:r.x+bl+pl+(w-e.naturalWidth*k)/2,y:r.y+bt+pt+(h-e.naturalHeight*k)/2,width:e.naturalWidth*k,height:e.naturalHeight*k},scale:k}});\n"""
            data=data.replace(b'      const cdp =',probe.encode()+b'      const cdp =')
        target.write_bytes(data)
    source=subprocess.check_output(['git','show',f'{ref}:backend/app/services/template_v3.py'],cwd=ROOT).decode('utf-8')
    mod=types.ModuleType('phase15_pinned_review');sys.modules[mod.__name__]=mod
    exec(compile(source,'phase15_pinned_review.py','exec'),mod.__dict__);mod.ROOT=root
    (root/'provenance.json').write_text(json.dumps({'ref':ref,'git_blob_hashes':hashes,'change':'worker import points to existing Playwright; extra read-only painted-image measurement; DOM/styles/PNG unchanged'},indent=2),encoding='utf-8')
    return mod.render_templates


def write_rows(folder,rows):
    for row in rows:
        filename=row['template_id']+'.png';(folder/filename).write_bytes(row.pop('png'));row['file']=filename


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--photo-inventory',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or out==ROOT or ROOT in out.parents:parser.error('Use a new output folder outside repository')
    inventory=json.loads(args.photo_inventory.read_text(encoding='utf-8'))
    # These indices were visually confirmed as the user's aburasoba, not inferred
    # from arbitrary filename matching. Refuse changed inventory/source hashes.
    real={}
    for key,i in [('real-cutout',15),('real-original',10)]:
        record=inventory[i];raw=Path(record['path']).read_bytes()
        if sha256(raw).hexdigest()!=record['sha256']:parser.error('Photo changed; inspect source again')
        real[key]=raw
    out.mkdir(parents=True)
    old=baseline(out/'pinned-phase15')
    cases=[('real-cutout','aburasoba',real['real-cutout']),('real-original','aburasoba',real['real-original']),
           ('cosmetic','cosmetic',complex_photo((500,1000),True,False)),
           ('clothing','clothing',sample('shirt',(1000,550),False,True)),
           ('long-cosmetic','cosmetic',complex_photo((500,1000),True,True))]
    fixtures=json.loads((ROOT/'tests/fixtures/copy/ad_quality_v1.json').read_text(encoding='utf-8'))
    all_results=[]
    for name,fixture_name,raw in cases:
        folder=out/name;folder.mkdir();case=fixtures[fixture_name]
        draft=InputDraft.model_validate({'facts':case['facts'],'product_features':case['product_features'],'mood':'warm'})
        variants=validate_copy(json.dumps({'variants':case['variants']},ensure_ascii=False),draft).variants
        rows=[];before_rows=[];inputs={}
        for variant in variants:
            data=TemplateInput(draft.facts.store_name,draft.facts.product_name,draft.facts.price_text,**variant.ad_copy.model_dump())
            if name=='long-cosmetic':data=replace(data,product_name='나만의 시간에 사용하는 데일리 로션',body='나만의 공간에 놓을 데일리 로션과 함께 오늘의 장면을 떠올려보세요.',original_price='15,000원',discount_text='20%',promotion_text='테스트 행사',period_text='2026.11.16–2026.11.20')
            ids=[variant.strategy+'_'+c for c in 'abcd']
            inputs.update({tid:asdict(data) for tid in ids})
            if name=='real-cutout':
                before=old(data,raw,ids);before_folder=out/'before';before_folder.mkdir(exist_ok=True);write_rows(before_folder,before);before_rows.extend(before)
            try:
                result=render_templates(data,raw,ids);write_rows(folder,result);rows.extend(result)
            except RenderFailure as error:
                (folder/'failure.json').write_text(json.dumps({'code':error.code,'measurement':getattr(error,'measurement',None)},ensure_ascii=False,indent=2),encoding='utf-8');raise
            print(name,variant.strategy,'OK',flush=True)
        metadata={'fixture':fixture_name,'source_sha256':sha256(raw).hexdigest(),'user_photo_local_only':name.startswith('real-'),
                  'facts':draft.facts.model_dump(),'inputs':inputs,'input_copies':[v.model_dump(mode='json',by_alias=True) for v in variants],'results':rows}
        (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
        if before_rows:(out/'before/metadata.json').write_text(json.dumps({'source_sha256':sha256(raw).hexdigest(),'results':before_rows},ensure_ascii=False,indent=2),encoding='utf-8')
        all_results.extend(rows)
    def gallery(path,html):path.write_text('<!doctype html><meta charset="UTF-8"><title>Phase16 local review</title><style>body{font-family:sans-serif;background:#eee;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%;height:auto}figcaption{padding:8px}@media(max-width:600px){body{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'+html,encoding='utf-8')
    gallery(out/'gallery.html',''.join(f'<figure><img src="real-cutout/{s}_{c}.png"><figcaption>{s}_{c}</figcaption></figure>' for s in NAMES for c in 'abcd'))
    gallery(out/'price-before-after.html',''.join(f'<figure><img src="{version}/price_{c}.png"><figcaption>{version} price_{c}</figcaption></figure>' for c in 'abcd' for version in ['before','real-cutout']))
    gallery(out/'all-conditions.html',''.join(f'<figure><img src="{name}/{s}_{c}.png"><figcaption>{name} {s}_{c}</figcaption></figure>' for name,_,_ in cases for s in NAMES for c in 'abcd'))
    for strategy in NAMES:gallery(out/f'{strategy}.html',''.join(f'<figure><img src="real-cutout/{strategy}_{c}.png"><figcaption>{strategy}_{c}</figcaption></figure>' for c in 'abcd'))
    sheet=Image.new('RGB',(1080,1420),'#eee')
    for i,(s,c) in enumerate((s,c) for s in NAMES for c in 'abcd'):
        im=Image.open(out/'real-cutout'/f'{s}_{c}.png');im.thumbnail((270,337));sheet.paste(im,((i%4)*270,(i//4)*355))
    sheet.save(out/'gallery.png')
    (out/'summary.json').write_text(json.dumps({'new_pngs':len(all_results),'baseline_pngs':16,'rights':'User-provided food photo permitted for local testing only; other scenes original synthetic assets. No public upload.'},indent=2),encoding='utf-8')


if __name__=='__main__':main()
