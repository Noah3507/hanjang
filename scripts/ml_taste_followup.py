"""Step 9-7: check the TASTE-only model before using it as a secondary design-preference signal.

Run from the repository root, inside .venv-ml:
  python scripts/ml_taste_followup.py

Follows up step 9-6 (agreed with A on 2026-10-30). The test split is never read.
1. Wider L2 grid for the TASTE-only model (CLIP + stats), 5-fold CV over TASTE
   train+val split groups (same outer folds as step 9-6).
2. Nested CV: inside each outer fold, L2 is chosen by a 4-fold inner CV on the
   training groups only, so the outer accuracy is not inflated by choosing the
   best of many settings.
3. Score combination check: s = s_cr / sd_cr + alpha * s_taste / sd_taste
   (each score divided by its standard deviation on its own training images).
   Reported on CreativeRanking val pairs and on TASTE outer folds.
Decision rules, fixed before running:
- TASTE model as a secondary signal (option 2): nested gain over cr_only > 2 SE.
- Combination (option 3): only if some alpha > 0 raises CreativeRanking val
  accuracy over alpha = 0 by more than 2 SE; otherwise the scores stay separate.
Models are fitted with ml.training.bt_logistic (same code and input checks as
step 9). Writes data/evaluation/taste-followup-v1/results.json (ignored by Git).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # allow "python scripts/..." from the repo root

from ml.data.outputs import code_revision, describe_inputs, staged_output
from ml.training.bt_logistic import ImageFeatures, PairSet, Scaler, fit_bt, pair_set, pairwise_accuracy, scores

FEATURES = "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"
SPLITS = "data/processed/splits/split-v1"
VERSION = "taste-followup-v1"
OUTER_SALT = "taste-experiment-v1"  # same outer folds as step 9-6
FOLDS, INNER_FOLDS = 5, 4
CR_L2 = 0.1  # chosen in step 9 (CreativeRanking-first rule)
L2_GRID = [0.1, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0]
ALPHAS = [0.0, 0.1, 0.25, 0.5, 1.0]


def fold_of(group: str, salt: str, folds: int) -> int:
    return int(hashlib.sha256(f"{salt}:{group}".encode()).hexdigest(), 16) % folds


def make_set(x: np.ndarray, ra: np.ndarray, rb: np.ndarray, y: np.ndarray) -> PairSet:
    n = len(y)
    return PairSet(x[ra], x[rb], y.astype(np.float64), np.full(n, 1.0 / max(n, 1)), np.full(n, "taste"))


def fit_on(x: np.ndarray, ra: np.ndarray, rb: np.ndarray, y: np.ndarray, l2: float):
    """Scaler on the training images of these pairs, then the Bradley-Terry weights."""
    scaler = Scaler.fit(x[np.unique(np.concatenate([ra, rb]))])
    return scaler, fit_bt(make_set(x, ra, rb, y), scaler, l2)


def accuracy_of(score: np.ndarray, ra: np.ndarray, rb: np.ndarray, y: np.ndarray) -> float:
    return pairwise_accuracy(score[ra], score[rb], y)


def choose_l2(x, ra, rb, y, groups) -> tuple[float, dict]:
    """Inner CV on training groups only; best vote-weighted accuracy, ties -> larger L2."""
    inner = np.array([fold_of(g, VERSION + "-inner", INNER_FOLDS) for g in groups])
    result = {}
    for l2 in L2_GRID:
        correct = 0.0
        for j in range(INNER_FOLDS):
            tr, te = inner != j, inner == j
            if not tr.any() or not te.any():
                continue
            scaler, w = fit_on(x, ra[tr], rb[tr], y[tr], l2)
            correct += accuracy_of(scores(x, scaler, w), ra[te], rb[te], y[te]) * te.sum()
        result[l2] = correct / len(y)
    best = max(L2_GRID, key=lambda l2: (result[l2], l2))
    return best, result


def gain_summary(accs: np.ndarray, reference: np.ndarray, pairs: np.ndarray) -> dict:
    gain = accs - reference
    return {"cv_accuracy": float((accs * pairs).sum() / pairs.sum()),
            "fold_accuracy": [float(a) for a in accs],
            "gain_vs_cr_only": float(gain.mean()),
            "gain_se": float(gain.std(ddof=1) / np.sqrt(len(gain)))}


def run(repo_root: Path) -> dict:
    feature_dir, split_dir = repo_root / FEATURES, repo_root / SPLITS
    version = Path(FEATURES).name
    taste_f = ImageFeatures.load(feature_dir, "taste", version)
    cr_f = ImageFeatures.load(feature_dir, "creativeranking", version)

    # The selected step 9 model: CreativeRanking train pairs, l2 = CR_L2 (same as scripts/ml_train.py).
    cr_pairs = pd.read_parquet(split_dir / "creativeranking.parquet")
    cr_train, cr_val = (pair_set(cr_pairs, cr_f, s, "creativeranking") for s in ("train", "val"))
    cr_train_rows = cr_f.rows(pd.concat([cr_pairs.loc[cr_pairs["split"] == "train", c] for c in ("image_a", "image_b")]))
    cr_scaler = Scaler.fit(cr_f.matrix[np.unique(cr_train_rows)])
    w_cr = fit_bt(cr_train, cr_scaler, CR_L2)
    sd_cr = float(scores(cr_f.matrix[np.unique(cr_train_rows)], cr_scaler, w_cr).std())
    s_cr_taste = scores(taste_f.matrix, cr_scaler, w_cr)
    cr_val_a, cr_val_b = scores(cr_val.a, cr_scaler, w_cr), scores(cr_val.b, cr_scaler, w_cr)

    taste = pd.read_parquet(split_dir / "taste.parquet")
    taste = taste[taste["split"].isin(["train", "val"])].reset_index(drop=True)  # test never read
    x = taste_f.matrix
    ra, rb = taste_f.rows(taste["image_a"]), taste_f.rows(taste["image_b"])
    y, groups = taste["a_wins"].to_numpy(), taste["split_group"].to_numpy()
    outer = np.array([fold_of(g, OUTER_SALT, FOLDS) for g in groups])

    flat = {l2: [] for l2 in L2_GRID}
    nested, cr_only, pairs, chosen = [], [], [], []
    combo_taste = {a: [] for a in ALPHAS}
    for k in range(FOLDS):
        tr, te = outer != k, outer == k
        pairs.append(int(te.sum()))
        cr_only.append(accuracy_of(s_cr_taste, ra[te], rb[te], y[te]))
        for l2 in L2_GRID:
            scaler, w = fit_on(x, ra[tr], rb[tr], y[tr], l2)
            flat[l2].append(accuracy_of(scores(x, scaler, w), ra[te], rb[te], y[te]))
        best, _ = choose_l2(x, ra[tr], rb[tr], y[tr], groups[tr])
        chosen.append(best)
        scaler, w = fit_on(x, ra[tr], rb[tr], y[tr], best)
        s_t = scores(x, scaler, w)
        nested.append(accuracy_of(s_t, ra[te], rb[te], y[te]))
        sd_t = float(s_t[np.unique(np.concatenate([ra[tr], rb[tr]]))].std())
        for alpha in ALPHAS:
            combo = s_cr_taste / sd_cr + alpha * s_t / sd_t
            combo_taste[alpha].append(accuracy_of(combo, ra[te], rb[te], y[te]))
        print(f"fold {k + 1}/{FOLDS}: chosen l2={best:g}, nested acc {nested[-1]:.4f}, cr_only {cr_only[-1]:.4f}",
              flush=True)

    pairs_arr, ref = np.array(pairs), np.array(cr_only)
    # Final TASTE model on all TASTE train+val with the most often chosen L2 (ties -> larger), for the CR val check.
    counts = Counter(chosen)
    final_l2 = max(counts, key=lambda l2: (counts[l2], l2))
    t_scaler, w_t = fit_on(x, ra, rb, y, final_l2)
    sd_t_all = float(scores(x[np.unique(np.concatenate([ra, rb]))], t_scaler, w_t).std())
    t_val_a, t_val_b = scores(cr_val.a, t_scaler, w_t), scores(cr_val.b, t_scaler, w_t)
    p0 = pairwise_accuracy(cr_val_a, cr_val_b, cr_val.y)
    cr_val_se = float(np.sqrt(p0 * (1 - p0) / len(cr_val.y)))
    combination = []
    for alpha in ALPHAS:
        cr_acc = pairwise_accuracy(cr_val_a / sd_cr + alpha * t_val_a / sd_t_all,
                                   cr_val_b / sd_cr + alpha * t_val_b / sd_t_all, cr_val.y)
        combination.append({"alpha": alpha, "creativeranking_val_accuracy": cr_acc,
                            "taste_cv_accuracy": float((np.array(combo_taste[alpha]) * pairs_arr).sum()
                                                       / pairs_arr.sum())})

    nested_summary = gain_summary(np.array(nested), ref, pairs_arr)
    best_combo = max((c for c in combination if c["alpha"] > 0), key=lambda c: c["creativeranking_val_accuracy"])
    decisions = {
        "taste_secondary_signal": bool(nested_summary["gain_vs_cr_only"] > 2 * nested_summary["gain_se"]),
        "combine_scores": bool(best_combo["creativeranking_val_accuracy"] - p0 > 2 * cr_val_se),
    }
    return {
        "flat_cv": {str(l2): gain_summary(np.array(flat[l2]), ref, pairs_arr) for l2 in L2_GRID},
        "nested_cv": {**nested_summary, "chosen_l2_per_fold": chosen},
        "cr_only_cv_accuracy": float((ref * pairs_arr).sum() / pairs_arr.sum()),
        "final_taste_l2": final_l2,
        "creativeranking_val": {"pairs": int(len(cr_val.y)), "cr_model_accuracy": p0, "se": cr_val_se},
        "combination": combination,
        "decisions": decisions,
        "taste_votes": int(len(taste)),
    }


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    result = run(repo_root)
    print("\nwider L2 grid (TASTE-only, 5-fold CV, not nested):")
    for l2, s in result["flat_cv"].items():
        print(f"  l2={float(l2):<7g} CV acc {s['cv_accuracy']:.4f}  gain {s['gain_vs_cr_only']:+.4f} ± {s['gain_se']:.4f}")
    n = result["nested_cv"]
    print(f"\nnested CV: acc {n['cv_accuracy']:.4f}, gain vs cr_only {n['gain_vs_cr_only']:+.4f} ± {n['gain_se']:.4f}, "
          f"chosen l2 per fold {n['chosen_l2_per_fold']} (cr_only {result['cr_only_cv_accuracy']:.4f})")
    v = result["creativeranking_val"]
    print(f"\ncombination (final TASTE l2={result['final_taste_l2']:g}; CR val {v['pairs']} pairs, "
          f"CR model {v['cr_model_accuracy']:.4f} ± {v['se']:.4f}):")
    for c in result["combination"]:
        print(f"  alpha={c['alpha']:<5g} CR val {c['creativeranking_val_accuracy']:.4f}  TASTE CV {c['taste_cv_accuracy']:.4f}")
    print("\ndecisions:", result["decisions"])
    inputs = {"taste_split_pairs": repo_root / SPLITS / "taste.parquet",
              "creativeranking_split_pairs": repo_root / SPLITS / "creativeranking.parquet",
              "feature_manifest": repo_root / FEATURES / "manifest.json"}
    report = {"version": VERSION, "evaluated_on": "TASTE train+val CV and CreativeRanking val (test never read)",
              "config": {"l2_grid": L2_GRID, "alphas": ALPHAS, "cr_l2": CR_L2, "folds": FOLDS,
                         "inner_folds": INNER_FOLDS},
              **result, "code": code_revision(repo_root), "inputs": describe_inputs(inputs, repo_root),
              "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with staged_output(repo_root / "data/evaluation" / VERSION) as tmp:
        (tmp / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote data/evaluation/{VERSION}/results.json")
    return report


if __name__ == "__main__":
    main()
