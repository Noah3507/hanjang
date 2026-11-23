"""Offline original-photo validation and analysis; never overwrite the source."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.services.uploads import validate_image
from app.services.photo_processor import LocalRembg,process_photo
from app.services.analysis_execution import AnalysisExecution
from app.services.analysis_palette import extract_palette
from app.schemas.analysis import ClipResult


def prepare_photo(photo,output):
    if output.exists():raise ValueError('Use a new photo review directory')
    raw=photo.read_bytes();before=sha256(raw).hexdigest()
    width,height,mime=validate_image(raw,'image/jpeg' if photo.suffix.lower() in ('.jpg','.jpeg') else 'image/png')
    output.mkdir(parents=True)
    result=process_photo(raw,LocalRembg(ROOT/'artifacts/models/rembg/u2netp.onnx'))
    if result.png:(output/'derived-cutout.png').write_bytes(result.png)
    if result.mask_png:(output/'derived-mask.png').write_bytes(result.mask_png)
    palette=extract_palette(raw)
    canonical=ROOT/'artifacts/models/analysis/ViT-B-32.pt';model=canonical
    if canonical.is_file() and sha256(canonical.read_bytes()).hexdigest()!='40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af':
        raise ValueError('Unexpected CLIP weights; no replacement/download')
    # Reuse an existing verified junction; do not create a new system link/config.
    links=Path(os.environ.get('LOCALAPPDATA',''))/'HanJang/model-links'
    if links.is_dir():
        for link in links.iterdir():
            if link.is_dir() and link.resolve()==canonical.parent.resolve():
                model=link/canonical.name;break
    worker=AnalysisExecution(ROOT/'.venv-analysis/Scripts/python.exe',model)
    try:reply=worker(raw)
    finally:worker.close()
    clip=ClipResult.model_validate(reply['clip'])
    report={'source_sha256':before,'selected_photo':'original','original_size':[width,height],'mime':mime,
            'original_unchanged':sha256(photo.read_bytes()).hexdigest()==before,
            'rembg':{'available':result.png is not None,'size':[result.width,result.height],'warnings':result.warnings},
            'clip':clip.model_dump(mode='json'),'palette':palette.model_dump(mode='json'),
            'analysis_warning':reply.get('warning'),'policy':'Analyze original once; reuse identical cues for both prompts. Derived cutout is review-only.'}
    if not report['original_unchanged']:raise ValueError('Source photo changed')
    (output/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--photo',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=prepare_photo(a.photo,a.output)
    print(json.dumps({'original_unchanged':r['original_unchanged'],'size':r['original_size'],'rembg':r['rembg']['available'],'clip':r['clip']['status'],'palette_colors':len(r['palette']['colors'])}))
