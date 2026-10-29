"""Compute and cache CLIP embeddings and image statistics for every pair image.

Run from the repository root, inside .venv-ml, after scripts/ml_fetch_images.py:
  python scripts/ml_extract_features.py --time-only 200   # speed check, writes nothing
  python scripts/ml_extract_features.py                   # full run

Reads the split pairs (data/processed/splits/split-v1/) and the images in
data/raw/, writes data/features/<feature_version>/ (ignored by Git):
  <dataset>_index.parquet               row, image, split, had_alpha
  <dataset>_clip.npy                    padded (pad-square-v1) embeddings, L2-normalized
  <dataset>_stats.npy                   brightness, contrast, saturation, n_colors
  <dataset>_center_crop_index.parquet   val/test images only
  <dataset>_clip_center_crop.npy        center-crop embeddings, for the evaluation comparison
  manifest.json                         model, versions, column order, counts, code commit, inputs
The folder is replaced only when every image succeeds and every value is finite.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.clip_config import PRETRAINED_TAG
from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.features.clip_features import DEFAULT_MODEL, ClipEncoder, feature_version, open_image
from ml.features.image_stats import STAT_NAMES, STATS_VERSION, image_stats

DATASETS = ("taste", "creativeranking")
EVAL_SPLITS = ("val", "test")


def inside_data(path: Path, repo_root: Path) -> Path:
    data_root = (repo_root / "data").resolve()
    target = (path if path.is_absolute() else repo_root / path).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"folder must be inside {data_root}, got {target}")
    return target


def image_table(pairs: pd.DataFrame) -> pd.DataFrame:
    """One row per image with its split (step 6 guarantees one split per image)."""
    images = pd.concat([
        pairs[["image_a", "split"]].rename(columns={"image_a": "image"}),
        pairs[["image_b", "split"]].rename(columns={"image_b": "image"}),
    ]).drop_duplicates()
    if images["image"].duplicated().any():
        raise ValueError("an image belongs to several splits; rerun scripts/ml_split_pairs.py")
    return images.sort_values("image").reset_index(drop=True)


def encode_images(encoder: ClipEncoder, paths: list[Path], batch_size: int, with_crop: list[bool],
                  label: str) -> dict:
    """Embeddings (pad, and center crop where requested), stats and alpha flags."""
    clip, crop, stats, alpha = [], [], [], []
    start = time.time()
    for begin in range(0, len(paths), batch_size):
        batch_paths = paths[begin:begin + batch_size]
        opened = [open_image(p) for p in batch_paths]
        images = [image for image, _ in opened]
        alpha.extend(had_alpha for _, had_alpha in opened)
        stats.extend(image_stats(image) for image in images)
        clip.append(encoder.encode(images, mode="pad"))
        crop_images = [img for img, keep in zip(images, with_crop[begin:begin + batch_size]) if keep]
        if crop_images:
            crop.append(encoder.encode(crop_images, mode="center_crop"))
        done = begin + len(batch_paths)
        if done % (batch_size * 30) < batch_size or done == len(paths):
            rate = done / max(time.time() - start, 1e-9)
            print(f"  {label}: {done}/{len(paths)} images, {rate:.1f}/s, "
                  f"about {(len(paths) - done) / max(rate, 1e-9) / 60:.0f} min left", flush=True)
    dim = encoder.metadata()["embedding_dim"]
    return {
        "clip": np.concatenate(clip) if clip else np.zeros((0, dim), np.float32),
        "crop": np.concatenate(crop) if crop else np.zeros((0, dim), np.float32),
        "stats": np.stack(stats) if stats else np.zeros((0, len(STAT_NAMES)), np.float32),
        "alpha": alpha,
    }


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict | None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", type=Path, default=Path("data/processed/splits/split-v1"))
    parser.add_argument("--taste-images", type=Path, default=Path("data/raw/taste"))
    parser.add_argument("--cr-images", type=Path, default=Path("data/raw/creativeranking/images"))
    parser.add_argument("--out", type=Path, default=Path("data/features"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pretrained", default=PRETRAINED_TAG, help="'none' = random weights (tests)")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--time-only", type=int, default=0, metavar="N",
                        help="encode the first N CreativeRanking images, print the speed, write nothing")
    args = parser.parse_args(argv)
    try:
        out_root = inside_data(args.out, repo_root)
    except ValueError as error:
        parser.error(str(error))
    split_dir = args.splits if args.splits.is_absolute() else repo_root / args.splits
    roots = {"taste": repo_root / args.taste_images, "creativeranking": repo_root / args.cr_images}

    pretrained = None if args.pretrained == "none" else args.pretrained
    encoder = ClipEncoder.load(args.model, pretrained, device="cpu")
    meta = encoder.metadata()
    version = feature_version(meta, STATS_VERSION)

    tables = {ds: image_table(pd.read_parquet(split_dir / f"{ds}.parquet")) for ds in DATASETS}
    if args.time_only:
        table = tables["creativeranking"].head(args.time_only)
        start = time.time()
        encode_images(encoder, [roots["creativeranking"] / i for i in table["image"]], args.batch_size,
                      list(table["split"].isin(EVAL_SPLITS)), "time-only")
        rate = len(table) / max(time.time() - start, 1e-9)
        total = sum(len(t) for t in tables.values())
        print(f"{rate:.1f} images/s on CPU ({torch.get_num_threads()} threads) -> "
              f"about {total / rate / 60:.0f} min for all {total} images")
        return None

    inputs = {f"{ds}_split_pairs": split_dir / f"{ds}.parquet" for ds in DATASETS}
    if (split_dir / "stats.json").exists():
        inputs["split_stats"] = split_dir / "stats.json"
    manifest = {
        "feature_version": version,
        "clip": meta,
        "stats": {"version": STATS_VERSION, "columns": list(STAT_NAMES), "source": "original image, no padding"},
        "alpha_policy": "transparent pixels filled with the pad color before everything else",
        "batch_size": args.batch_size,
        "torch_threads": torch.get_num_threads(),
        "code": code_revision(repo_root),
        "inputs": describe_inputs(inputs, repo_root),
        "datasets": {},
    }

    # Compute everything first; nothing is written unless all images succeed.
    results, start = {}, time.time()
    for ds, table in tables.items():
        paths = [roots[ds] / image for image in table["image"]]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            raise SystemExit(f"{len(missing)} {ds} images are missing, e.g. {missing[:3]}")
        with_crop = list(table["split"].isin(EVAL_SPLITS))
        out = encode_images(encoder, paths, args.batch_size, with_crop, ds)
        for name in ("clip", "crop", "stats"):
            if not np.isfinite(out[name]).all():
                raise ValueError(f"{ds} {name} has NaN or infinite values")
        table = table.assign(row=np.arange(len(table)), had_alpha=out["alpha"])
        crop_table = table[with_crop].assign(row=np.arange(int(np.sum(with_crop))))
        results[ds] = (table, crop_table, out)
        manifest["datasets"][ds] = {
            "images": len(table),
            "images_per_split": table["split"].value_counts().sort_index().to_dict(),
            "alpha_flattened": int(table["had_alpha"].sum()),
            "center_crop_images": len(crop_table),
        }
        print(f"{ds}:", manifest["datasets"][ds])
    manifest["elapsed_seconds"] = round(time.time() - start, 1)
    manifest["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    out_dir = out_root / version
    with staged_output(out_dir) as tmp:  # replaces out_dir only if all files are written
        for ds, (table, crop_table, out) in results.items():
            table[["row", "image", "split", "had_alpha"]].to_parquet(tmp / f"{ds}_index.parquet", index=False)
            crop_table[["row", "image", "split"]].to_parquet(tmp / f"{ds}_center_crop_index.parquet", index=False)
            np.save(tmp / f"{ds}_clip.npy", out["clip"], allow_pickle=False)
            np.save(tmp / f"{ds}_clip_center_crop.npy", out["crop"], allow_pickle=False)
            np.save(tmp / f"{ds}_stats.npy", out["stats"], allow_pickle=False)
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_dir}")
    return manifest


if __name__ == "__main__":
    main()
