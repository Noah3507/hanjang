"""Explicit pinned rembg download; defaults to the existing u2netp. Never run in CI."""
import argparse
from hashlib import sha256
from pathlib import Path
import urllib.request
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.services.photo_models import MODELS

URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
SIZE = 4574861
CHECKSUM = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    parser.add_argument('--model', choices=list(MODELS), default='u2netp')
    args = parser.parse_args()
    spec = MODELS[args.model]
    target = ROOT / 'artifacts/models/rembg' / (spec.name+'.onnx')
    if target.is_symlink():
        raise RuntimeError("Refusing a symlink model target")
    if target.exists():
        if target.stat().st_size != spec.size or sha256(target.read_bytes()).hexdigest() != spec.sha256:
            raise RuntimeError("Existing model checksum differs; file was not overwritten")
        print("Verified model already present; download skipped")
        return
    print(f"Downloading {spec.name}: {spec.size} bytes from {spec.url}")
    with urllib.request.urlopen(spec.url, timeout=90) as response:
        data = response.read(spec.size + 1)
    if len(data) != spec.size or sha256(data).hexdigest() != spec.sha256:
        raise RuntimeError("Model size/checksum mismatch; no model saved")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)
    print("Verified model saved in Git-excluded local cache")


if __name__ == "__main__":
    main()
