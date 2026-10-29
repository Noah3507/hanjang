"""Train the logistic Bradley-Terry model and keep the best setting on val.

Run from the repository root, inside .venv-ml, after scripts/ml_extract_features.py:
  python scripts/ml_train.py

Fits every (training set x L2) setting in ml/training/config.json on TRAIN
pairs only (scaler fit on train images only), picks the setting with the best
mean val pairwise accuracy over both datasets, and writes
artifacts/models/ranking/<version>/ (ignored by Git):
  model.safetensors    weights [n_features], scaler mean/std (float64, no pickle)
  model_config.json    feature order and versions needed to score a new image
  training_report.json every setting's val results, chosen setting, baselines, code commit, inputs
The test split is never read.
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
from safetensors.numpy import save_file

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.training.bt_logistic import (
    ImageFeatures,
    Scaler,
    concat,
    fit_bt,
    log_loss,
    pair_set,
    pairwise_accuracy,
    scores,
)

DATASETS = ("taste", "creativeranking")


def evaluate(sets: dict, scaler: Scaler, weights: np.ndarray) -> dict:
    result = {}
    for ds, s in sets.items():
        sa, sb = scores(s.a, scaler, weights), scores(s.b, scaler, weights)
        result[ds] = {"pairs": len(s.y), "accuracy": pairwise_accuracy(sa, sb, s.y), "log_loss": log_loss(sa, sb, s.y)}
    return result


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("ml/training/config.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/models/ranking"))
    args = parser.parse_args(argv)
    resolve = lambda p: p if p.is_absolute() else repo_root / p  # noqa: E731
    cfg = json.loads(resolve(args.config).read_text())
    feature_dir = repo_root / "data/features" / cfg["feature_version"]
    split_dir = repo_root / "data/processed/splits" / cfg["split_version"]
    torch.set_num_threads(max(1, torch.get_num_threads()))

    features = {ds: ImageFeatures.load(feature_dir, ds) for ds in DATASETS}
    pairs = {ds: pd.read_parquet(split_dir / f"{ds}.parquet") for ds in DATASETS}
    train = {ds: pair_set(pairs[ds], features[ds], "train", ds) for ds in DATASETS}
    val = {ds: pair_set(pairs[ds], features[ds], "val", ds) for ds in DATASETS}

    start, runs = time.time(), []
    for name, members in cfg["training_sets"].items():
        train_set = concat([train[ds] for ds in members])
        train_images = np.concatenate([
            features[ds].matrix[np.unique(np.concatenate([
                features[ds].rows(pairs[ds].loc[pairs[ds]["split"] == "train", "image_a"]),
                features[ds].rows(pairs[ds].loc[pairs[ds]["split"] == "train", "image_b"]),
            ]))] for ds in members
        ])
        scaler = Scaler.fit(train_images)  # train images only
        for l2 in cfg["l2"]:
            weights = fit_bt(train_set, scaler, l2, cfg["max_iter"])
            val_result = evaluate(val, scaler, weights)
            mean_acc = float(np.mean([val_result[ds]["accuracy"] for ds in DATASETS]))
            runs.append({"training_set": name, "l2": l2, "val": val_result, "mean_val_accuracy": mean_acc,
                         "train": evaluate({ds: train[ds] for ds in members}, scaler, weights),
                         "_model": (scaler, weights)})
            print(f"{name:16s} l2={l2:<7g} val acc " + "  ".join(
                f"{ds} {val_result[ds]['accuracy']:.4f}" for ds in DATASETS) + f"  mean {mean_acc:.4f}", flush=True)

    best = max(runs, key=lambda r: (r["mean_val_accuracy"], -r["l2"]))
    scaler, weights = best["_model"]
    columns = features[DATASETS[0]].columns
    baselines_path = repo_root / "data/evaluation/baselines-v1/results.json"
    baselines = None
    if baselines_path.exists():
        saved = json.loads(baselines_path.read_text())
        baselines = {ds: saved["datasets"][ds]["accuracy"] for ds in DATASETS}

    inputs = {f"{ds}_split_pairs": split_dir / f"{ds}.parquet" for ds in DATASETS}
    inputs["feature_manifest"] = feature_dir / "manifest.json"
    feature_manifest = json.loads((feature_dir / "manifest.json").read_text())
    model_config = {
        "model_version": cfg["version"],
        "method": "bradley_terry_sigmoid_v1",
        "score": "s = sum(weights * (features - scaler_mean) / scaler_std); P(A preferred) = sigmoid(s_A - s_B)",
        "feature_version": cfg["feature_version"],
        "feature_columns": columns,
        "clip": feature_manifest["clip"],
        "stats": feature_manifest["stats"],
        "training_set": best["training_set"],
        "l2": best["l2"],
    }
    report = {
        "model_version": cfg["version"],
        "config": cfg,
        "chosen": {k: best[k] for k in ("training_set", "l2", "mean_val_accuracy", "val")},
        "runs": [{k: v for k, v in r.items() if k != "_model"} for r in runs],
        "baselines_val_accuracy": baselines,
        "evaluated_on": "val (test split never read)",
        "elapsed_seconds": round(time.time() - start, 1),
        "torch": torch.__version__,
        "code": code_revision(repo_root),
        "inputs": describe_inputs(inputs, repo_root),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    out_dir = resolve(args.out) / cfg["version"]
    with staged_output(out_dir) as tmp:
        save_file({"weights": weights, "scaler_mean": scaler.mean, "scaler_std": scaler.std},
                  str(tmp / "model.safetensors"), metadata={"model_version": cfg["version"]})
        (tmp / "model_config.json").write_text(json.dumps(model_config, indent=2, ensure_ascii=False) + "\n")
        (tmp / "training_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"chosen: {best['training_set']} l2={best['l2']} mean val accuracy {best['mean_val_accuracy']:.4f}")
    print(f"wrote {out_dir}")
    return report


if __name__ == "__main__":
    main()
