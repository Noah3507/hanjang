"""Step 10: the one and only evaluation on the test split.

Run from the repository root, inside .venv-ml, after scripts/ml_train.py and
scripts/ml_train_taste.py:
  python scripts/ml_evaluate.py --check-only   # preflight: reads no test labels, writes nothing
  python scripts/ml_evaluate.py                # the single test run

The plan and the decision rules were fixed with A before the test run (see
ml/evaluation/README.md):
- frozen models: CreativeRanking model bt-logistic-v1 (service ranking) and
  TASTE model bt-taste-v1 (secondary design-preference reference)
- primary results: CreativeRanking model on CreativeRanking test pairs, TASTE
  model on TASTE test pairs; both models are also reported on the other set
- pairwise accuracy with 95% cluster bootstrap intervals; clusters are connected
  components of test pairs that share an image (TASTE: checked to equal the
  step 6 split_group), 2000 resamples, seed 0
- the primary model minus each baseline (random, train-chosen rule, LAION) with
  the same paired cluster bootstrap; the rule is the pre-declared strongest
  baseline (best on val for both datasets in step 8)
- Top-1 and Kendall's tau per ranking group, accuracy by score gap (val for the
  close-call threshold, test for confirmation), designer agreement (TASTE)
- center-crop sensitivity: the same padding-trained models with center-crop CLIP
  features of the test images (image statistics unchanged); not a retrained model
The results file is written once. If it exists the script stops; a rerun needs
A's approval, a written reason, and moving the old folder by hand.
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
from ml.data.split import image_components
from ml.evaluation.baselines import load_laion_linear, rule_accuracies
from ml.evaluation.metrics import (
    accuracy_by_score_gap,
    cluster_bootstrap,
    correct,
    creativeranking_product_groups,
    designer_agreement,
    ranking_metrics,
    same_partition,
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
STRUCTURE = ["image_a", "image_b", "group_id", "split", "split_group"]  # no labels


def test_clusters(test: pd.DataFrame, ds: str) -> np.ndarray:
    """Cluster id per test pair: groups (prompts / products) that share an image are merged."""
    clusters = test["group_id"].map(image_components(test, "group_id")).to_numpy()
    if ds == "taste" and not same_partition(clusters, test["split_group"].to_numpy()):
        raise ValueError("TASTE split_group does not match the image components of the test pairs")
    return clusters


def center_crop_matrix(feature_dir: Path, dataset: str, features: ImageFeatures) -> dict:
    """image -> [center-crop CLIP | stats] for val/test images; the statistics stay as they are."""
    index = pd.read_parquet(feature_dir / f"{dataset}_center_crop_index.parquet")
    crop = np.load(feature_dir / f"{dataset}_clip_center_crop.npy", allow_pickle=False).astype(np.float64)
    clip_dim = sum(c.startswith("clip_") for c in features.columns)
    if len(index) != len(crop) or crop.ndim != 2 or crop.shape[1] != clip_dim or not np.isfinite(crop).all():
        raise ValueError(f"{dataset}: center-crop features are missing, misaligned or not finite")
    rows = features.rows(index["image"])
    return {image: np.concatenate([crop[i], features.matrix[r, clip_dim:]])
            for i, (image, r) in enumerate(zip(index["image"], rows))}


def prepare(repo_root: Path, model_root: Path, skip_laion: bool) -> dict:
    """Load and check everything the test run needs, without reading any test label."""
    feature_dir, split_dir = repo_root / FEATURES, repo_root / SPLITS
    models = {name: load_model(model_root / version) for name, version in MODELS.items()}
    features = {ds: ImageFeatures.load(feature_dir, ds, Path(FEATURES).name) for ds in DATASETS}
    for name, (config, _, _) in models.items():
        if config["feature_version"] != Path(FEATURES).name or config["feature_columns"] != features["taste"].columns:
            raise ValueError(f"{name}: feature version or column order differs from the feature cache")
    laion = None if skip_laion else load_laion_linear(repo_root / LAION, 512)
    data = {}
    for ds in DATASETS:
        structure = pd.read_parquet(split_dir / f"{ds}.parquet", columns=STRUCTURE)
        test = structure[structure["split"] == "test"].reset_index(drop=True)
        wrong = test["image_a"].map(dict(zip(features[ds].images, features[ds].splits))).ne("test") | \
            test["image_b"].map(dict(zip(features[ds].images, features[ds].splits))).ne("test")
        if wrong.any():
            raise ValueError(f"{ds}: {int(wrong.sum())} test pairs use images outside the cached test split")
        crop = center_crop_matrix(feature_dir, ds, features[ds])
        missing = (set(test["image_a"]) | set(test["image_b"])) - set(crop)
        if missing:
            raise ValueError(f"{ds}: {len(missing)} test images have no center-crop features")
        clusters = test_clusters(test, ds)
        data[ds] = {"crop": crop, "summary": {
            "test_pairs": int(len(test)), "groups": int(test["group_id"].nunique()),
            "clusters": int(pd.Series(clusters).nunique()),
            "split_group_matches_components": ds == "taste" or None}}
    inputs = {f"{ds}_split_pairs": split_dir / f"{ds}.parquet" for ds in DATASETS}
    inputs["feature_manifest"] = feature_dir / "manifest.json"
    for name, version in MODELS.items():
        inputs[f"{name}_weights"] = model_root / version / "model.safetensors"
        inputs[f"{name}_config"] = model_root / version / "model_config.json"
    if laion is not None:
        inputs["laion_weights"] = repo_root / LAION
    return {"models": models, "features": features, "laion": laion, "data": data, "inputs": inputs}


def baseline_credits(pairs, features, test, ra, rb, y, laion) -> dict:
    clip_dim = sum(c.startswith("clip_") for c in features.columns)
    stats, stat_names = features.matrix[:, clip_dim:], features.columns[clip_dim:]
    train = pairs[pairs["split"] == "train"]
    tr_a, tr_b = features.rows(train["image_a"]), features.rows(train["image_b"])
    train_rules = rule_accuracies(stats[tr_a], stats[tr_b], train["a_wins"].to_numpy(), stat_names)
    rule = max(sorted(train_rules), key=lambda k: train_rules[k])
    col, sign = stat_names.index(rule[:-1]), (1.0 if rule.endswith("+") else -1.0)
    guess_a = np.random.default_rng(SEED).random(len(y)) < 0.5
    credits = {"random": (guess_a == y.astype(bool)).astype(float),
               "rule": correct(sign * stats[ra, col], sign * stats[rb, col], y)}
    if laion is not None:
        weight, bias = laion
        clip = features.matrix[:, : len(weight)]
        credits["laion_aesthetic"] = correct(clip[ra] @ weight + bias, clip[rb] @ weight + bias, y)
    return credits, rule


def decide(ds: str, primary: dict) -> dict:
    """Decision rules fixed before the test run (ml/evaluation/README.md)."""
    acc_low = primary["accuracy"]["ci95"][0]
    vs_rule_low = primary["difference_vs_baselines"]["rule"]["ci95"][0]
    if ds == "creativeranking":
        use = acc_low > 0.5 and vs_rule_low > 0 and primary["ranking"]["top1"] > primary["ranking"]["top1_random"]
        return {"creativeranking_model": "use for the service ranking" if use else
                "hold: keep MockRanker in the service, report the result, no tuning on test"}
    use = acc_low > 0.5 and vs_rule_low > 0
    return {"taste_model": "show as a separate design-preference reference" if use else
            "report only: not shown in the service"}


def evaluate_dataset(ds, pairs, features, crop, models, laion) -> dict:
    test = pairs[pairs["split"] == "test"].reset_index(drop=True)
    pair_set(pairs, features, "test", ds)  # every test image must be a test image in the cache
    ra, rb = features.rows(test["image_a"]), features.rows(test["image_b"])
    y, clusters = test["a_wins"].to_numpy(), test_clusters(test, ds)
    images = sorted(set(test["image_a"]) | set(test["image_b"]))
    base, rule = baseline_credits(pairs, features, test, ra, rb, y, laion)
    out = {"pairs": int(len(test)), "clusters": int(pd.Series(clusters).nunique()), "models": {},
           "baselines": {k: cluster_bootstrap(v, clusters, REPS, SEED) for k, v in base.items()},
           "rule_chosen_on_train": rule}

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
            "accuracy": cluster_bootstrap(credit, clusters, REPS, SEED),
            "difference_vs_baselines": {k: cluster_bootstrap(credit - v, clusters, REPS, SEED) for k, v in base.items()},
            "ranking": ranking_metrics(rank_groups),
            "accuracy_by_score_gap": accuracy_by_score_gap(s[ra] - s[rb], credit),
            "center_crop_sensitivity": {
                "note": "same padding-trained model, test images encoded with center crop; statistics unchanged",
                "accuracy": cluster_bootstrap(crop_credit, clusters, REPS, SEED),
                "padding_minus_center_crop": cluster_bootstrap(credit - crop_credit, clusters, REPS, SEED)},
        }
    if ds == "taste":
        out["designer_agreement_reference"] = designer_agreement(test)
    out["decision"] = decide(ds, out["models"][PRIMARY[ds]])
    return out


def val_score_gaps(pairs: pd.DataFrame, features: ImageFeatures, model) -> list[dict]:
    """CreativeRanking val bins for choosing the close-call threshold without the test split."""
    config, scaler, weights = model
    val = pair_set(pairs, features, "val", "creativeranking")
    diff = scores(val.a, scaler, weights) - scores(val.b, scaler, weights)
    return accuracy_by_score_gap(diff, correct(diff, np.zeros_like(diff), val.y))


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", type=Path, default=Path("artifacts/models/ranking"))
    parser.add_argument("--skip-laion", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="check inputs; read no test labels, write nothing")
    args = parser.parse_args(argv)
    out_dir = repo_root / "data/evaluation" / VERSION
    if out_dir.exists():
        raise SystemExit(f"{out_dir} already exists: the test split is evaluated only once "
                         "(a rerun needs A's approval, a written reason and moving this folder by hand)")
    model_root = args.models if args.models.is_absolute() else repo_root / args.models
    ready = prepare(repo_root, model_root, args.skip_laion)
    if args.check_only:
        for ds, d in ready["data"].items():
            print(f"{ds}: {d['summary']}")
        for name, (config, _, _) in ready["models"].items():
            print(f"{name}: {config['model_version']} ({len(config['feature_columns'])} features)")
        print("inputs:", {k: v["sha256"][:12] for k, v in describe_inputs(ready["inputs"], repo_root).items()})
        print("ready: no test labels were read and nothing was written")
        return {"check_only": True, **{ds: d["summary"] for ds, d in ready["data"].items()}}

    split_dir = repo_root / SPLITS
    report = {"version": VERSION, "evaluated_on": "test (once)", "seed": SEED, "bootstrap_reps": REPS,
              "primary": PRIMARY, "datasets": {}}
    for ds in DATASETS:
        pairs = pd.read_parquet(split_dir / f"{ds}.parquet")
        report["datasets"][ds] = evaluate_dataset(ds, pairs, ready["features"][ds], ready["data"][ds]["crop"],
                                                  ready["models"], ready["laion"])
    cr_pairs = pd.read_parquet(split_dir / "creativeranking.parquet")
    report["creativeranking_val_score_gaps"] = val_score_gaps(cr_pairs, ready["features"]["creativeranking"],
                                                              ready["models"]["creativeranking_model"])
    report.update({"device": "cpu", "torch": torch.__version__, "code": code_revision(repo_root),
                   "inputs": describe_inputs(ready["inputs"], repo_root),
                   "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    with staged_output(out_dir) as tmp:
        (tmp / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    fmt = lambda r: f"{r['mean']:+.4f} [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}]"  # noqa: E731
    acc = lambda r: f"{r['mean']:.4f} [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]"  # noqa: E731
    bins = lambda b: ", ".join(f"{x['gap_from']}-{x['gap_to'] or 'inf'}: "  # noqa: E731
                               + (f"{x['accuracy']:.3f}" if x["accuracy"] is not None else "-") + f" ({x['pairs']})"
                               for x in b)
    for ds, res in report["datasets"].items():
        print(f"\n{ds} test: {res['pairs']} pairs, {res['clusters']} clusters, rule = {res['rule_chosen_on_train']}")
        for name, m in res["models"].items():
            mark = "  <- primary" if PRIMARY[ds] == name else ""
            print(f"  {name:22s} acc {acc(m['accuracy'])}  top1 {m['ranking']['top1']:.3f} "
                  f"(random {m['ranking']['top1_random']:.3f})  tau {m['ranking']['kendall_tau']:+.3f}{mark}")
            print(f"  {'':22s} minus rule {fmt(m['difference_vs_baselines']['rule'])}  "
                  f"center-crop input {acc(m['center_crop_sensitivity']['accuracy'])}  "
                  f"padding - crop {fmt(m['center_crop_sensitivity']['padding_minus_center_crop'])}")
        for name, b in res["baselines"].items():
            print(f"  baseline {name:16s} acc {acc(b)}")
        if "designer_agreement_reference" in res:
            print(f"  designer agreement (reference): {res['designer_agreement_reference']:.4f}")
        print(f"  primary model by score gap (test): {bins(res['models'][PRIMARY[ds]]['accuracy_by_score_gap'])}")
        print(f"  decision: {res['decision']}")
    print(f"\ncreativeranking model by score gap (val, for the close-call threshold): "
          f"{bins(report['creativeranking_val_score_gaps'])}")
    print(f"\nwrote data/evaluation/{VERSION}/results.json")
    return report


if __name__ == "__main__":
    main()
