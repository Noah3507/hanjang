"""Explicit offline load probe used by service_local.ps1, never by service startup/CI."""
from io import BytesIO
import os
from pathlib import Path
from PIL import Image, ImageDraw
from app.services.photo_processor import LocalRembg
from app.services.analysis_execution import AnalysisExecution


def main():
    image = Image.new('RGB', (400, 300), 'white')
    ImageDraw.Draw(image).ellipse((100, 40, 300, 260), fill='orange')
    # Loading and inference only: no quality assertion about this synthetic mask.
    mask = LocalRembg(Path(os.environ['HANJANG_PHOTO_MODEL_PATH']))(image)
    if mask.size != image.size:
        raise RuntimeError('rembg output dimensions mismatch')
    raw = BytesIO(); image.save(raw, 'PNG')
    worker = AnalysisExecution(Path(os.environ['HANJANG_ANALYSIS_PYTHON']), Path(os.environ['HANJANG_ANALYSIS_MODEL_PATH']))
    try:
        result = worker(raw.getvalue())
        if result['clip']['status'] != 'available':
            raise RuntimeError(result.get('warning', 'CLIP_UNAVAILABLE'))
    finally:
        worker.close()
    print('Offline rembg and CLIP model loading/inference OK')


if __name__ == '__main__':
    main()
