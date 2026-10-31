"""Build the offline model bundle the service loads (step 11).

Run from the repository root, inside .venv-ml, after scripts/ml_train.py:
  python scripts/ml_build_bundle.py

Turns artifacts/models/ranking/bt-logistic-v1/ (written by scripts/ml_train.py)
into a bundle: adds clip/ViT-B-32-openai-visual.safetensors (the CLIP image
tower from the local open_clip cache) and manifest.json with SHA-256, sizes and
package versions. Before the folder is replaced, the new bundle is loaded with
ml.inference.load_model and checked against the training feature cache: for a
sample of cached val images the inference features must equal the cached ones
(CLIP within 1e-5, statistics within 1e-6), so training and serving compute the
same numbers. The result of that check is saved in bundle_report.json (not
listed in the manifest). Nothing is uploaded; artifacts/ is ignored by Git.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, staged_output
from ml.features.clip_features import ClipEncoder, open_image
from ml.features.image_stats import image_stats
from ml.inference import RankInput, load_model, rank_ads
from ml.inference.bundle import write_bundle

MODEL = "artifacts/models/ranking/bt-logistic-v1"
FIXTURES = "tests/fixtures/ads"


def cache_check(model, feature_dir: Path, image_root: Path, dataset: str, sample: int) -> dict:
    """Inference features of cached val images must equal the training feature cache."""
    index = pd.read_parquet(feature_dir / f"{dataset}_index.parquet")
    clip = np.load(feature_dir / f"{dataset}_clip.npy", allow_pickle=False)
    stats = np.load(feature_dir / f"{dataset}_stats.npy", allow_pickle=False)
    rows = index[index["split"] == "val"].head(sample)
    worst_clip = worst_stats = 0.0
    for row, image in zip(rows["row"], rows["image"]):
        picture, _ = open_image(image_root / image)
        got_clip = model._encoder.encode([picture], mode="pad")[0]
        got_stats = image_stats(picture)
        worst_clip = max(worst_clip, float(np.abs(got_clip - clip[row]).max()))
        worst_stats = max(worst_stats, float(np.abs(got_stats - stats[row]).max()))
    ok = worst_clip <= 1e-5 and worst_stats <= 1e-6
    return {"images": int(len(rows)), "max_abs_diff_clip": worst_clip, "max_abs_diff_stats": worst_stats, "ok": ok}


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT, encoder: ClipEncoder | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=Path(MODEL))
    parser.add_argument("--sample", type=int, default=32, help="cached val images to compare")
    parser.add_argument("--skip-cache-check", action="store_true", help="tests only")
    args = parser.parse_args(argv)
    model_dir = args.model_dir if args.model_dir.is_absolute() else repo_root / args.model_dir
    if not (model_dir / "model.safetensors").exists():
        raise SystemExit(f"{model_dir} has no model.safetensors; run scripts/ml_train.py first")
    config = json.loads((model_dir / "model_config.json").read_text())
    encoder = encoder or ClipEncoder.load(config["clip"]["model"], config["clip"]["pretrained"])

    with staged_output(model_dir) as tmp:  # the old folder stays until every check passes
        manifest = write_bundle(model_dir, tmp, encoder, code_revision(repo_root))
        model = load_model(tmp, model_file=tmp / "model.safetensors")
        fixtures = sorted((repo_root / FIXTURES).glob("*.png"))
        ranking = rank_ads([RankInput(p.stem, p) for p in fixtures], model) if len(fixtures) == 4 else None
        report = {"model_version": manifest["model_version"], "manifest_files": manifest["files"],
                  "fixture_ranking": ranking,
                  "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if not args.skip_cache_check:
            feature_dir = repo_root / "data/features" / config["feature_version"]
            report["cache_check"] = {
                "creativeranking": cache_check(model, feature_dir, repo_root / "data/raw/creativeranking/images",
                                               "creativeranking", args.sample)}
            if not report["cache_check"]["creativeranking"]["ok"]:
                raise SystemExit(f"inference features differ from the training cache: {report['cache_check']}")
        (tmp / "bundle_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    total = sum(f["bytes"] for f in manifest["files"].values())
    print(f"bundle {manifest['model_version']}: {len(manifest['files'])} files, {total / 1e6:.1f} MB")
    for name, f in manifest["files"].items():
        print(f"  {name}: {f['bytes'] / 1e6:.1f} MB sha256 {f['sha256'][:16]}...")
    if "cache_check" in report:
        print("cache check:", report["cache_check"])
    if ranking:
        print("fixture ranking:", [(i["candidate_id"], round(i["score"], 4), i["rank"]) for i in ranking["items"]])
    print(f"wrote {model_dir}")
    return report


if __name__ == "__main__":
    main()
