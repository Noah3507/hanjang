"""Measure CPU memory and latency of one CLIP candidate on 4 ads (batch).

Run one model per command so the peak memory belongs to that model:
  python scripts/ml_benchmark_clip.py --model ViT-B-32
  python scripts/ml_benchmark_clip.py --model ViT-B-16
  python scripts/ml_benchmark_clip.py --model ViT-L-14

The first run downloads the pretrained weights (hundreds of MB to over
1 GB) into the Hugging Face cache, outside the repository. Results are
printed and saved to artifacts/benchmarks/ (ignored by Git).
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import open_clip
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.clip_config import CLIP_CANDIDATES, PRETRAINED_TAG, embedding_dim, input_size, uses_quick_gelu
from ml.device import select_device
from ml.features.preprocess import (
    DEFAULT_PAD_COLOR,
    PREPROCESSING_VERSION,
    load_rgb,
    pad_to_square,
)

DEFAULT_IMAGES = REPO_ROOT / "tests" / "fixtures" / "ads"


def peak_rss_mb() -> float:
    """Peak resident memory of this process so far, in MB."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux reports kilobytes.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, choices=CLIP_CANDIDATES)
    parser.add_argument("--pretrained", default=PRETRAINED_TAG,
                        help="'none' builds random weights (no download, timing only)")
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--device", default="cpu", help="cpu (deployment) or auto")
    parser.add_argument("--warm-runs", type=int, default=5)
    args = parser.parse_args()

    torch.manual_seed(0)
    device = select_device(None if args.device == "auto" else args.device)
    pretrained = None if args.pretrained == "none" else args.pretrained
    paths = sorted(args.images.glob("*.png"))[:4]
    if len(paths) != 4:
        raise SystemExit(f"need 4 PNG files in {args.images}, found {len(paths)}")

    # openai weights were trained with QuickGELU; build the model to match them.
    quick_gelu = pretrained is not None and uses_quick_gelu(args.model, pretrained)
    rss_before = peak_rss_mb()
    start = time.perf_counter()
    model, _, preprocess = open_clip.create_model_and_transforms(
        args.model, pretrained=pretrained, device=device, force_quick_gelu=quick_gelu
    )
    model.eval()
    load_s = time.perf_counter() - start
    rss_after_load = peak_rss_mb()

    # Pad to square first, so open_clip's resize + center crop removes nothing.
    batch = torch.stack(
        [preprocess(pad_to_square(load_rgb(p), DEFAULT_PAD_COLOR)) for p in paths]
    ).to(device)

    with torch.no_grad():
        start = time.perf_counter()
        features = model.encode_image(batch)
        cold_s = time.perf_counter() - start
        warm = []
        for _ in range(args.warm_runs):
            start = time.perf_counter()
            model.encode_image(batch)
            warm.append(time.perf_counter() - start)

    result = {
        "model": args.model,
        "pretrained": args.pretrained,
        "quick_gelu": quick_gelu,
        "device": str(device),
        "torch_threads": torch.get_num_threads(),
        "preprocessing_version": PREPROCESSING_VERSION,
        "pad_color": list(DEFAULT_PAD_COLOR),
        "input_size": input_size(args.model),
        "embedding_dim_config": embedding_dim(args.model),
        "embedding_dim_output": int(features.shape[-1]),
        "batch_size": len(paths),
        "load_seconds": round(load_s, 2),
        "cold_batch_seconds": round(cold_s, 3),
        "warm_batch_seconds_median": round(statistics.median(warm), 3),
        "peak_rss_mb_before_load": round(rss_before, 1),
        "peak_rss_mb_after_load": round(rss_after_load, 1),
        "peak_rss_mb_after_inference": round(peak_rss_mb(), 1),
        "machine": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "open_clip": open_clip.__version__,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(json.dumps(result, indent=2))
    out_dir = REPO_ROOT / "artifacts" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clip_{args.model}_{args.pretrained}.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"saved {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
