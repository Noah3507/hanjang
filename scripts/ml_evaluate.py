"""Step 10: the one and only evaluation on the test split.

Run from the repository root, inside .venv-ml, after scripts/ml_train.py and
scripts/ml_train_taste.py:
  python scripts/ml_evaluate.py

The plan was fixed with A before this ran (see ml/evaluation/README.md):
- models (frozen): CreativeRanking model bt-logistic-v1 (service ranking) and
  TASTE model bt-taste-v1 (secondary design-preference reference)
- primary results: CreativeRanking model on CreativeRanking test pairs,
  TASTE model on TASTE test pairs; both models are also reported on the other set
- metrics: pairwise accuracy with a 95% cluster bootstrap interval (groups =
  products / TASTE image components, 2000 resamples, seed 0), Top-1 and Kendall's
  tau per ranking group, accuracy by predicted confidence, designer agreement (TASTE)
- baselines on the same test pairs: random (seed 0), the image-statistic rule
  chosen on train pairs, LAION aesthetic score
- padding vs center crop: the same models scored with center-crop CLIP features
  of the test images (paired bootstrap of the difference)
The results folder is written once; running again refuses to overwrite it
(--allow-overwrite exists only for a rerun after a crash before writing).
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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.evaluation.baselines import load_laion_linear, rule_accuracies
from ml.evaluation.metrics import (
    accuracy_by_confidence,
    cluster_bootstrap,
    correct,
    creativeranking_product_groups,
    designer_agreement,
    ranking_metrics,
    taste_vote_groups,
)
from ml.training.bt_logistic import ImageFeatures, load_model, pair_set, scores

DATASETS = ("creativeranking", "taste")
MODELS = {"creativeranking_model": "bt-logistic-v1", "taste_model": "bt-taste-v1"}
PRIMARY = {"creativeranking": "creativeranking_model", "taste": "taste_model"}
FEATURES = "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"
SPLITS = "data/processed/splits/split-v1"
LAION = "data/raw/laion/sa_0_4_vit_b_32_linear.pth"
VERSION = "final-test-v1"
SEED, REPS = 0, 2000


def center_crop_matrix(feature_dir: Path, dataset: str, features: ImageFeatures) -> dict:
    """image -> [center-crop CLIP | stats] row for the val/test images (stats do not depend on the crop)."""
    index = pd.read_parquet(feature_dir / f"{dataset}_center_crop_index.parquet")
    crop = np.load(feature_dir / f"{dataset}_clip_center_crop.npy", allow_pickle=False).astype(np.float64)
    clip_dim = sum(c.startswith("clip_") for c in features.columns)
    if len(index) != len(crop) or crop.ndim != 2 or crop.shape[1] != clip_dim or not np.isfinite(crop).all():
        raise ValueError(f"{dataset}: center-crop features are missing, misaligned or not finite")
    rows = features.rows(index["image"])
    return {image: np.concatenate([crop[i], features.matrix[r, clip_dim:]])
            for i, (image, r) in enumerate(zip(index["image"], rows))}


def evaluate_dataset(ds, pairs, features, crop, models, laion) -> dict:
    test = pairs[pairs["split"] == "test"].reset_index(drop=True)
    pair_set(pairs, features, "test", ds)  # every test image must be a test image in the cache
    ra, rb = features.rows(test["image_a"]), features.rows(test["image_b"])
    y, groups = test["a_wins"].to_numpy(), test["split_group"].to_numpy()
    images = sorted(set(test["image_a"]) | set(test["image_b"]))
    out = {"pairs": int(len(test)), "groups": int(pd.Series(groups).nunique()), "models": {}, "baselines": {}}

    for name, (config, scaler, weights) in models.items():
        s = scores(features.matrix, scaler, weights)
        credit = correct(s[ra], s[rb], y)
        image_score = dict(zip(features.images, s))
        rank_groups = (creativeranking_product_groups(test, image_score) if ds == "creativeranking"
                       else taste_vote_groups(test, image_score))
        crop_score = {i: float(scores(crop[i][None, :], scaler, weights)[0]) for i in images}
        crop_credit = correct(test["image_a"].map(crop_score).to_numpy(), test["image_b"].map(crop_score).to_numpy(), y)
        out["models"][name] = {
            "model_version": config["model_version"],
            "accuracy": cluster_bootstrap(credit, groups, REPS, SEED),
            "ranking": ranking_metrics(rank_groups),
            "accuracy_by_confidence": accuracy_by_confidence(s[ra] - s[rb], credit),
            "center_crop_accuracy": cluster_bootstrap(crop_credit, groups, REPS, SEED),
            "padding_minus_center_crop": cluster_bootstrap(credit - crop_credit, groups, REPS, SEED),
        }

    train = pairs[pairs["split"] == "train"]
    clip_dim = sum(c.startswith("clip_") for c in features.columns)
    stats, stat_names = features.matrix[:, clip_dim:], features.columns[clip_dim:]
    tr_a, tr_b = features.rows(train["image_a"]), features.rows(train["image_b"])
    train_rules = rule_accuracies(stats[tr_a], stats[tr_b], train["a_wins"].to_numpy(), stat_names)
    rule = max(sorted(train_rules), key=lambda k: train_rules[k])
    col, sign = stat_names.index(rule[:-1]), (1.0 if rule.endswith("+") else -1.0)
    guess_a = np.random.default_rng(SEED).random(len(y)) < 0.5
    baselines = {"random": (guess_a == y.astype(bool)).astype(float),
                 f"rule ({rule}, chosen on train)": correct(sign * stats[ra, col], sign * stats[rb, col], y)}
    if laion is not None:
        weight, bias = laion
        clip = features.matrix[:, : len(weight)]
        baselines["laion_aesthetic"] = correct(clip[ra] @ weight + bias, clip[rb] @ weight + bias, y)
    out["baselines"] = {k: cluster_bootstrap(v, groups, REPS, SEED) for k, v in baselines.items()}
    if ds == "taste":
        out["designer_agreement"] = designer_agreement(test)
    return out


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", type=Path, default=Path("artifacts/models/ranking"))
    parser.add_argument("--skip-laion", action="store_true")
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args(argv)
    out_dir = repo_root / "data/evaluation" / VERSION
    if (out_dir / "results.json").exists() and not args.allow_overwrite:
        raise SystemExit(f"{out_dir}/results.json already exists: the test split is evaluated only once")
    model_root = args.models if args.models.is_absolute() else repo_root / args.models
    feature_dir, split_dir = repo_root / FEATURES, repo_root / SPLITS

    models = {name: load_model(model_root / version) for name, version in MODELS.items()}
    features = {ds: ImageFeatures.load(feature_dir, ds, Path(FEATURES).name) for ds in DATASETS}
    for name, (config, _, _) in models.items():
        if config["feature_version"] != Path(FEATURES).name or config["feature_columns"] != features["taste"].columns:
            raise ValueError(f"{name}: feature version or column order differs from the feature cache")
    laion = None if args.skip_laion else load_laion_linear(repo_root / LAION, 512)

    inputs = {f"{ds}_split_pairs": split_dir / f"{ds}.parquet" for ds in DATASETS}
    inputs["feature_manifest"] = feature_dir / "manifest.json"
    for name, version in MODELS.items():
        inputs[f"{name}_weights"] = model_root / version / "model.safetensors"
        inputs[f"{name}_config"] = model_root / version / "model_config.json"
    if laion is not None:
        inputs["laion_weights"] = repo_root / LAION

    report = {"version": VERSION, "evaluated_on": "test (once)", "seed": SEED, "bootstrap_reps": REPS,
              "primary": PRIMARY, "datasets": {}}
    for ds in DATASETS:
        pairs = pd.read_parquet(split_dir / f"{ds}.parquet")
        crop = center_crop_matrix(feature_dir, ds, features[ds])
        report["datasets"][ds] = evaluate_dataset(ds, pairs, features[ds], crop, models, laion)

    report.update({"device": "cpu", "torch": torch.__version__, "code": code_revision(repo_root),
                   "inputs": describe_inputs(inputs, repo_root),
                   "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    with staged_output(out_dir) as tmp:
        (tmp / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    fmt = lambda r: f"{r['mean']:.4f} [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]"  # noqa: E731
    for ds, res in report["datasets"].items():
        print(f"\n{ds} test: {res['pairs']} pairs, {res['groups']} groups")
        for name, m in res["models"].items():
            mark = "  <- primary" if PRIMARY[ds] == name else ""
            print(f"  {name:22s} acc {fmt(m['accuracy'])}  top1 {m['ranking']['top1']:.3f} "
                  f"(random {m['ranking']['top1_random']:.3f})  tau {m['ranking']['kendall_tau']:+.3f}{mark}")
            print(f"  {'':22s} center crop {fmt(m['center_crop_accuracy'])}  "
                  f"padding - crop {m['padding_minus_center_crop']['mean']:+.4f} "
                  f"[{m['padding_minus_center_crop']['ci95'][0]:+.4f}, {m['padding_minus_center_crop']['ci95'][1]:+.4f}]")
        for name, b in res["baselines"].items():
            print(f"  baseline {name:31s} acc {fmt(b)}")
        if "designer_agreement" in res:
            print(f"  designer agreement (votes matching the pair majority): {res['designer_agreement']:.4f}")
        primary = res["models"][PRIMARY[ds]]["accuracy_by_confidence"]
        print("  primary model accuracy by confidence: " + ", ".join(
            f"{b['p_from']:.2f}-{b['p_to']:.2f}: {b['accuracy']:.3f} ({b['pairs']})" if b["accuracy"] is not None
            else f"{b['p_from']:.2f}-{b['p_to']:.2f}: - (0)" for b in primary))
    print(f"\nwrote data/evaluation/{VERSION}/results.json")
    return report


if __name__ == "__main__":
    main()
