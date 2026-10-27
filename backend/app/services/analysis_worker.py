"""A-owned, offline JSON-lines worker. No B module imports."""
import base64
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys
import time

MODEL_SHA = '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af'

def peak_memory_mib():
    if os.name != 'nt':
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024**2 if sys.platform == 'darwin' else 1024)
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak', 'working', 'qp', 'q', 'qnp', 'qn', 'pf', 'ppf')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters(); counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return counters.peak / 1024**2

def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    model = text = preprocess = None
    load_error = None
    for line in sys.stdin:
        message = json.loads(line)
        start = time.perf_counter()
        load_seconds = 0.
        try:
            if model is None and load_error is None:
                path = Path(sys.argv[1])
                if not path.is_file():
                    load_error = 'ANALYSIS_MODEL_UNAVAILABLE'
                else:
                    with path.open('rb') as stream:
                        digest = sha256()
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(chunk)
                    if digest.hexdigest() != MODEL_SHA:
                        load_error = 'ANALYSIS_MODEL_INVALID'
                if load_error is None:
                    import torch
                    import open_clip
                    from app.services.analysis_prompts import CANDIDATES
                    torch.set_num_threads(min(4, os.cpu_count() or 1))
                    # Official OpenAI artifact is TorchScript, not a weights_only checkpoint.
                    # This loader builds the matching QuickGELU model from the verified local archive.
                    from open_clip.openai import load_openai_model
                    from open_clip.transform import image_transform
                    model = load_openai_model(str(path), device='cpu', precision='fp32')
                    preprocess = image_transform(224, is_train=False,
                        mean=model.visual.image_mean, std=model.visual.image_std, interpolation='bicubic')
                    model.eval()
                    with torch.inference_mode():
                        text = model.encode_text(open_clip.get_tokenizer('ViT-B-32')([c[3] for c in CANDIDATES]))
                        text = text / text.norm(dim=-1, keepdim=True)
                    load_seconds = time.perf_counter()-start
            if load_error:
                raise ValueError(load_error)
            from PIL import Image, ImageOps
            from app.services.analysis_prompts import CANDIDATES
            import torch
            with Image.open(BytesIO(base64.b64decode(message['data']))) as image:
                if image.width * image.height > 24_000_000:
                    raise ValueError('ANALYSIS_IMAGE_INVALID')
                rgba = ImageOps.exif_transpose(image).convert('RGBA')
                rgb = Image.new('RGB', rgba.size, 'white')
                rgb.paste(rgba, mask=rgba.getchannel('A'))
                side = max(rgb.size)
                padded = Image.new('RGB', (side, side), 'white')
                padded.paste(rgb, ((side-rgb.width)//2, (side-rgb.height)//2))
                batch = preprocess(padded).unsqueeze(0)
            inference_start = time.perf_counter()
            with torch.inference_mode():
                feature = model.encode_image(batch)
                feature = feature / feature.norm(dim=-1, keepdim=True)
                scores = (feature @ text.T)[0].tolist()
            if len(scores) != len(CANDIDATES) or not all(math.isfinite(score) for score in scores):
                raise ValueError('ANALYSIS_CLIP_FAILED')
            cues = [dict(category=c[0], candidate_id=c[1], label=c[2], similarity=max(-1., min(1., s)))
                    for c, s in zip(CANDIDATES, scores)]
            body = {'clip': {'status': 'available', 'cues': cues}, 'warning': None,
                    'inference_seconds': time.perf_counter()-inference_start}
        except Exception as error:
            code = str(error) if str(error).startswith('ANALYSIS_') else 'ANALYSIS_CLIP_FAILED'
            if model is None:
                load_error = code
            body = {'clip': {'status': 'unavailable', 'cues': []}, 'warning': code}
        body.update(request_id=message['request_id'], elapsed_seconds=time.perf_counter()-start,
                    model_load_seconds=load_seconds, worker_pid=os.getpid(), peak_working_set_mib=peak_memory_mib())
        print(json.dumps(body, allow_nan=False), flush=True)

if __name__ == '__main__':
    main()
