"""Verify selected, already provisioned photo weights. No inference/network."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.photo_models import MODELS, model_file_verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=MODELS, required=True)
    parser.add_argument('--path', type=Path, required=True)
    args = parser.parse_args()
    if not model_file_verified(args.path, args.model):
        print('Photo model verification failed; check selected name, file and checksum. No download performed.')
        return 1
    print(f'Photo model verified: {args.model}. No inference/download performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
