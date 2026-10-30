"""Train the TASTE design-preference model chosen in step 9-7 (secondary reference only).

Run from the repository root, inside .venv-ml:
  python scripts/ml_train_taste.py

Fits the logistic Bradley-Terry model of ml/training/bt_logistic.py on TASTE
train+val pairs with the L2 fixed in ml/training/taste_config.json (chosen by
nested CV in step 9-7, so no further selection happens here). Every vote counts
equally. Writes artifacts/models/ranking/<version>/ (ignored by Git) in the same
format as scripts/ml_train.py. The service ranking keeps using the
CreativeRanking model; this model is a separate design-preference reference.
The test split is never read.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from safetensors.numpy import save_file

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.training.bt_logistic import ImageFeatures, Scaler, concat, fit_bt, pair_set, pairwise_accuracy, scores


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("ml/training/taste_config.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/models/ranking"))
    args = parser.parse_args(argv)
    resolve = lambda p: p if p.is_absolute() else repo_root / p  # noqa: E731
    cfg = json.loads(resolve(args.config).read_text())
    if "test" in cfg["train_splits"]:
        raise ValueError("the test split must not be used for training")
    feature_dir = repo_root / "data/features" / cfg["feature_version"]
    split_path = repo_root / "data/processed/splits" / cfg["split_version"] / "taste.parquet"

    features = ImageFeatures.load(feature_dir, "taste", cfg["feature_version"])
    pairs = pd.read_parquet(split_path)
    train = concat([pair_set(pairs, features, s, "taste") for s in cfg["train_splits"]])  # checks image splits
    train.weight = np.full(len(train.y), 1.0 / len(train.y))  # every vote counts equally
    used = pairs[pairs["split"].isin(cfg["train_splits"])]
    rows = np.unique(np.concatenate([features.rows(used["image_a"]), features.rows(used["image_b"])]))
    scaler = Scaler.fit(features.matrix[rows])
    weights = fit_bt(train, scaler, cfg["l2"], cfg["max_iter"])
    train_acc = pairwise_accuracy(scores(train.a, scaler, weights), scores(train.b, scaler, weights), train.y)

    manifest = json.loads((feature_dir / "manifest.json").read_text())
    model_config = {
        "model_version": cfg["version"],
        "method": "bradley_terry_sigmoid_v1",
        "score": "s = sum(weights * (features - scaler_mean) / scaler_std); P(A preferred) = sigmoid(s_A - s_B)",
        "feature_version": cfg["feature_version"],
        "feature_columns": features.columns,
        "clip": manifest["clip"],
        "stats": manifest["stats"],
        "training_set": "taste",
        "trained_on_splits": cfg["train_splits"],
        "l2": cfg["l2"],
        "role": cfg["role"],
    }
    report = {
        "model_version": cfg["version"], "config": cfg, "train_votes": int(len(train.y)),
        "train_accuracy": train_acc, "evaluated_on": "none here (test is evaluated once in step 10)",
        "torch": torch.__version__, "code": code_revision(repo_root),
        "inputs": describe_inputs({"taste_split_pairs": split_path, "feature_manifest": feature_dir / "manifest.json"},
                                  repo_root),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_dir = resolve(args.out) / cfg["version"]
    with staged_output(out_dir) as tmp:
        save_file({"weights": weights, "scaler_mean": scaler.mean, "scaler_std": scaler.std},
                  str(tmp / "model.safetensors"), metadata={"model_version": cfg["version"]})
        (tmp / "model_config.json").write_text(json.dumps(model_config, indent=2, ensure_ascii=False) + "\n")
        (tmp / "training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"trained {cfg['version']} on {len(train.y)} TASTE votes (l2={cfg['l2']}), train accuracy {train_acc:.4f}")
    print(f"wrote {out_dir}")
    return report


if __name__ == "__main__":
    main()
