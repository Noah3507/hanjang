"""Isolated CPU inference process, terminated by parent on timeout."""
import base64
import json
from pathlib import Path
import sys

from app.services.photo_processor import LocalRembg, process_photo

if __name__ == "__main__":
    result = process_photo(sys.stdin.buffer.read(), LocalRembg(Path(sys.argv[1]), sys.argv[3] if len(sys.argv)>3 else 'u2netp'),
                           int(sys.argv[2]), matte_mode=sys.argv[4] if len(sys.argv)>4 else 'cleanup')
    print(json.dumps({"png": base64.b64encode(result.png).decode() if result.png else None,
                      "mask": base64.b64encode(result.mask_png).decode() if result.mask_png else None,
                      "width": result.width, "height": result.height, "warnings": result.warnings,
                      "processing_version": result.processing_version}))
