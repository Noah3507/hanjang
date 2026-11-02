"""A-owned offline worker; B owns all feature extraction and scoring."""
import json
from pathlib import Path
import sys
import time


def main():
    model_file=Path(sys.argv[1]);root=Path(sys.argv[2]).resolve()
    model=None;stamp=None;loads=0
    for line in sys.stdin:
        ticket=None
        try:
            message=json.loads(line);ticket=message['request_id']
            from ml.inference import RankInput, load_model, rank_ads
            from ml.inference import ModelNotAvailable, ArtifactMismatch, InvalidImage
            import torch
            torch.set_num_threads(4)
            # A changed bundle is revalidated by B's loader, never patched by A.
            current=tuple(sorted((str(p.relative_to(model_file.parent)),p.stat().st_size,p.stat().st_mtime_ns)
                for p in model_file.parent.rglob('*') if p.is_file()))
            loading=time.perf_counter();load_seconds=0.
            if model is None or stamp!=current:
                model=load_model(model_file.parent,model_file=model_file)
                load_seconds=time.perf_counter()-loading;loads+=1;stamp=current
            items=[]
            for item in message['items']:
                path=Path(item['rendered_image_path']).resolve(strict=True)
                if not path.is_relative_to(root): raise ValueError('Invalid snapshot')
                items.append(RankInput(item['candidate_id'],path))
            start=time.perf_counter();result=rank_ads(items,model)
            from app.services.analysis_worker import peak_memory_mib
            body={'result':result,'metrics':{'load_seconds':load_seconds,'inference_seconds':time.perf_counter()-start,'model_loads':loads,
                'peak_working_set_mib':peak_memory_mib()}}
        except Exception as error:
            # Never forward B/library exception text, paths, or tracebacks.
            code={'ModelNotAvailable':'RANKING_MODEL_UNAVAILABLE','ArtifactMismatch':'RANKING_ARTIFACT_INVALID',
                'InvalidImage':'RANKING_IMAGE_INVALID'}.get(type(error).__name__,'RANKING_INFERENCE_FAILED')
            body={'error':code};model=None;stamp=None
        body['request_id']=ticket
        print(json.dumps(body,allow_nan=False),flush=True)


if __name__=='__main__': main()
