"""Score the simple baselines on the validation pairs (the test split stays untouched).

Run from the repository root, inside .venv-ml, after scripts/ml_extract_features.py:
  python scripts/ml_baselines.py

Reads the split pairs and the step 7 feature cache, writes
data/evaluation/baselines-v1/results.json (ignored by Git). The rule baseline
picks its statistic and direction on train pairs; every baseline is then
scored on the same val pairs of each dataset. The LAION weights are read
from data/raw/laion/ (see ml/README.md); --skip-laion leaves that one out.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.evaluation.baselines import (
    FeatureCache,
    load_laion_linear,
    pairwise_accuracy,
    random_accuracy,
    rule_accuracies,
    standard_error,
)

DATASETS = ("taste", "creativeranking")
FEATURES = "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"
LAION = "data/raw/laion/sa_0_4_vit_b_32_linear.pth"
VERSION = "baselines-v1"
SEED = 0


def inside_data(path: Path, repo_root: Path) -> Path:
    data_root = (repo_root / "data").resolve()
    target = (path if path.is_absolute() else repo_root / path).resolve()
    if target == data_root or not target.is_relative_to(data_root):
        raise ValueError(f"folder must be inside {data_root}, got {target}")
    return target


def evaluate_dataset(pairs: pd.DataFrame, cache: FeatureCache, laion) -> dict:
    train = pairs[pairs["split"] == "train"]
    val = pairs[pairs["split"] == "val"]
    tr_a, tr_b = cache.rows(train["image_a"]), cache.rows(train["image_b"])
    va_a, va_b = cache.rows(val["image_a"]), cache.rows(val["image_b"])
    y_train, y_val = train["a_wins"].to_numpy(), val["a_wins"].to_numpy()

    train_rules = rule_accuracies(cache.stats[tr_a], cache.stats[tr_b], y_train, cache.stat_names)
    best_rule = max(sorted(train_rules), key=lambda name: train_rules[name])
    val_rules = rule_accuracies(cache.stats[va_a], cache.stats[va_b], y_val, cache.stat_names)

    n = len(val)
    accuracy = {
        "random": random_accuracy(y_val, SEED),
        f"rule ({best_rule}, chosen on train)": val_rules[best_rule],
    }
    if laion is not None:
        weight, bias = laion
        accuracy["laion_aesthetic"] = pairwise_accuracy(
            cache.clip[va_a] @ weight + bias, cache.clip[va_b] @ weight + bias, y_val
        )
    return {
        "val_pairs": n,
        "train_pairs": len(train),
        "accuracy": accuracy,
        "standard_error": {name: standard_error(acc, n) for name, acc in accuracy.items()},
        "rule_train_accuracy": train_rules,
        "rule_val_accuracy_all": val_rules,
    }


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--splits", type=Path, default=Path("data/processed/splits/split-v1"))
    parser.add_argument("--features", type=Path, default=Path(FEATURES))
    parser.add_argument("--laion", type=Path, default=Path(LAION))
    parser.add_argument("--skip-laion", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("data/evaluation"))
    args = parser.parse_args(argv)
    try:
        out_dir = inside_data(args.out, repo_root) / VERSION
    except ValueError as error:
        parser.error(str(error))
    resolve = lambda p: p if p.is_absolute() else repo_root / p  # noqa: E731
    split_dir, feature_dir, laion_path = resolve(args.splits), resolve(args.features), resolve(args.laion)

    inputs = {f"{ds}_split_pairs": split_dir / f"{ds}.parquet" for ds in DATASETS}
    inputs["feature_manifest"] = feature_dir / "manifest.json"
    laion = None
    if not args.skip_laion:
        if not laion_path.exists():
            parser.error(f"LAION weights not found at {laion_path} (download them or use --skip-laion)")
        inputs["laion_weights"] = laion_path
    results = {
        "version": VERSION,
        "evaluated_on": "val",
        "seed": SEED,
        "code": code_revision(repo_root),
        "inputs": describe_inputs(inputs, repo_root),
        "datasets": {},
    }
    for ds in DATASETS:
        cache = FeatureCache.load(feature_dir, ds)
        if not args.skip_laion and laion is None:
            laion = load_laion_linear(laion_path, cache.clip.shape[1])
        pairs = pd.read_parquet(inputs[f"{ds}_split_pairs"])
        results["datasets"][ds] = evaluate_dataset(pairs, cache, laion)
        summary = {k: round(v, 4) for k, v in results["datasets"][ds]["accuracy"].items()}
        print(f"{ds} (val pairs {results['datasets'][ds]['val_pairs']}):", summary)

    results["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with staged_output(out_dir) as tmp:
        (tmp / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_dir / 'results.json'}")
    return results


if __name__ == "__main__":
    main()
