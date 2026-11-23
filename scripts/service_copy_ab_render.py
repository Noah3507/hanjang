"""Read saved A/B replies and use the unchanged v2 renderer; no API calls."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.schemas.upload import InputDraft
from app.services.copy_validation import validate_copy
from app.services.render_execution import RenderExecution,RenderFailure


def render_review(experiment,output,photo=None,renderer='v2'):
    if output.exists():raise ValueError('Use a new output directory')
    plan=json.loads((experiment/'plan.json').read_text(encoding='utf-8'))
    run=json.loads((experiment/'run.json').read_text(encoding='utf-8'))
    sources=[ROOT/'backend/app/services/render_execution.py',ROOT/'scripts/service_render_worker.mjs',*sorted((ROOT/'templates').glob('*.html')),ROOT/'templates/tokens.css']
    if renderer=='v3-a':
        sources += [ROOT/'backend/app/services/template_v3.py',ROOT/'scripts/service_render_v3_worker.mjs',*sorted((ROOT/'templates/v3').glob('*'))]
    elif renderer!='v2':raise ValueError('Unknown fixed renderer')
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sources}
    d=InputDraft.model_validate(plan['draft'])
    from io import BytesIO
    from PIL import Image,ImageDraw
    if photo:
        raw=photo.read_bytes();photo_status='user_selected_local_photo; identity must be visually confirmed as jajang'
        if not plan.get('photo') or sha256(raw).hexdigest()!=plan['photo']['sha256']:raise ValueError('Photo differs from approved plan')
    else:
        if plan.get('photo'):raise ValueError('Approved original photo required; do not silently substitute placeholder')
        im=Image.new('RGB',(640,480),'#ddd');ImageDraw.Draw(im).text((35,225),'PHOTO NOT SUPPLIED - LAYOUT CHECK ONLY',fill='#555')
        buffer=BytesIO();im.save(buffer,'PNG');raw=buffer.getvalue();photo_status='placeholder_not_product_photo'
    output.mkdir(parents=True);rows=[];executor=RenderExecution()
    prefix='real' if run['mode']=='real_openai' else 'offline-fake'
    for arm in ['A','B']:
        bound=experiment/arm/'bound.json'
        if not bound.is_file():
            rows.append({'arm':arm,'status':'unavailable_no_validated_response'});continue
        # Reuse original raw text for validation; never rewrite/cut to make it fit.
        copies=validate_copy((experiment/arm/'raw.txt').read_text(encoding='utf-8'),d)
        try:
            if renderer=='v2':results=executor(d,copies,raw)
            else:
                from app.services.template_v3 import TemplateInput,render_templates
                results=[]
                for v in copies.variants:
                    data=TemplateInput(d.facts.store_name,d.facts.product_name,d.facts.price_text,**v.ad_copy.model_dump())
                    results.extend(render_templates(data,raw,[v.strategy+'_a']))
        except RenderFailure as error:
            rows.append({'arm':arm,'status':'failed','error':error.code});continue
        for row in results:
            png=row.pop('png');name=prefix+'-'+arm+'-'+row['strategy']+'.png';(output/name).write_bytes(png)
            rows.append({'arm':arm,'strategy':row['strategy'],'file':name,'status':'rendered',
                         'png_sha256':sha256(png).hexdigest(),'measurement':row['measurement']})
    report={'mode':run['mode'],'renderer':renderer,'photo_status':photo_status,'photo_sha256':sha256(raw).hexdigest(),
            'renderer_source_hashes':hashes,'renderer_sources_unchanged_during_render':hashes=={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sources},
            'human_evaluation':'not_started','commercial_quality':'not_evaluated','results':rows}
    (output/'render-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    heading='REAL OPENAI COPY' if run['mode']=='real_openai' else 'OFFLINE TEST COPY — NOT LLM OUTPUT'
    html=f'<meta charset="UTF-8"><title>Hanjang A/B copy review</title><h1>{heading}</h1><p>{renderer}; {photo_status}; human review pending. AI aesthetic scores not assigned.</p><main>'
    # Order each strategy A/B side by side; existing layout stays identical.
    for strategy in ['emotional','price','visual','brand']:
        for arm in ['A','B']:
            name=prefix+'-'+arm+'-'+strategy+'.png'
            if (output/name).is_file():html+=f'<figure><img src="{name}"><figcaption>{arm} · {strategy}</figcaption></figure>'
    html+='</main><style>main{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}img{width:100%;height:auto}body{font-family:sans-serif}</style>'
    (output/'gallery.html').write_text(html,encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--renderer',choices=['v2','v3-a'],default='v2')
    p.add_argument('--photo',type=Path);args=p.parse_args()
    report=render_review(args.experiment,args.output,args.photo,args.renderer)
    print(json.dumps({'mode':report['mode'],'photo_status':report['photo_status'],'rendered_pngs':sum(r['status']=='rendered' for r in report['results'])}))


if __name__=='__main__':main()
