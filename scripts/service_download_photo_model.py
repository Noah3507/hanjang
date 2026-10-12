"""Explicit opt-in download of the fixed official u2netp artifact. Never run in CI."""
import argparse
from hashlib import sha256
from pathlib import Path
import urllib.request

URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
SIZE = 4574861
CHECKSUM = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "artifacts/models/rembg/u2netp.onnx"
    if target.is_symlink():
        raise RuntimeError("Refusing a symlink model target")
    if target.exists():
        if sha256(target.read_bytes()).hexdigest() != CHECKSUM:
            raise RuntimeError("Existing model checksum differs; file was not overwritten")
        print("Verified model already present; download skipped")
        return
    print(f"Downloading u2netp: {SIZE} bytes from {URL}")
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(SIZE + 1)
    if len(data) != SIZE or sha256(data).hexdigest() != CHECKSUM:
        raise RuntimeError("Model size/checksum mismatch; no model saved")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(data)
    print("Verified model saved in Git-excluded local cache")


if __name__ == "__main__":
    main()
