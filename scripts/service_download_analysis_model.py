"""Explicit approved OpenAI artifact download; not used at runtime or in CI."""
import argparse
from hashlib import sha256
from pathlib import Path
import urllib.request

CHECKSUM = '40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af'
URL = f'https://openaipublic.azureedge.net/clip/models/{CHECKSUM}/ViT-B-32.pt'
SIZE = 353976522

def checksum(path):
    digest = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', required=True)
    parser.parse_args()
    target = Path(__file__).resolve().parents[1] / 'artifacts/models/analysis/ViT-B-32.pt'
    if target.is_symlink():
        raise RuntimeError('Symlink target refused')
    if target.exists():
        if checksum(target) != CHECKSUM:
            raise RuntimeError('Existing artifact differs; not overwritten')
        print('Existing official model verified; skipped download')
        return
    print(f'Official source: {URL}\nExpected bytes: {SIZE}', flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    try:
        with urllib.request.urlopen(URL, timeout=120) as response, temporary.open('xb') as output:
            print(f'Response Content-Length: {response.headers.get("Content-Length")}', flush=True)
            total = 0
            for chunk in iter(lambda: response.read(1024*1024), b''):
                total += len(chunk)
                if total > SIZE:
                    raise RuntimeError('Artifact larger than expected')
                output.write(chunk)
        if total != SIZE or checksum(temporary) != CHECKSUM:
            raise RuntimeError('Size/checksum mismatch')
        temporary.rename(target)
        print(f'Verified {total} bytes, SHA256 {CHECKSUM}')
    finally:
        temporary.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
