"""Step 9-6: can the TASTE (designer preference) accuracy be improved?

Run from the repository root, inside .venv-ml, after scripts/ml_extract_features.py:
  python scripts/ml_taste_experiment.py

Compares cheap remedies for "too little TASTE data" with 5-fold cross-validation
over TASTE train+val split groups (images never shared across folds); the test
split is never read. Features are loaded with ml.training.bt_logistic.ImageFeatures,
so the same checks as training apply (feature version, widths, NaN/Inf, splits).
All models are linear Bradley-Terry scorers fitted by L-BFGS in float64
(deterministic). Methods:
  cr_only        the CreativeRanking model from step 9, no TASTE training (reference)
  full           CLIP 512 + stats 4, trained on TASTE folds, L2 grid
  stats_only     the 4 image statistics only
  pca            CLIP reduced by PCA (fit on training-fold images) + stats
  cr_prior       CreativeRanking score as a free feature + small TASTE correction (L2 on the correction)
  aux_dimensions "full" plus TASTE rankings of other criteria (color harmony, typography, ...) on
                 training-fold images, given the same total weight as the preference pairs
Combining the 5 votes of a pair into one soft label gives the same optimum as using
the votes separately (the logistic loss is linear in the label), so it is not tested.
Writes data/evaluation/taste-experiment-v1/results.json (ignored by Git).
"""

from __future__ import annotations

import argparse
import hashlib
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
from ml.training.bt_logistic import ImageFeatures

FEATURES = "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"
SPLITS = "data/processed/splits/split-v1"
VERSION = "taste-experiment-v1"
FOLDS = 5
CR_L2 = 0.1  # chosen in step 9 (CreativeRanking-first rule, 2026-10-30)
L2_GRID = [0.001, 0.01, 0.1, 1.0, 10.0]
PCA_DIMS = [8, 16, 32]


def load_features(feature_dir: Path, dataset: str) -> tuple[dict, np.ndarray, int]:
    """image -> row, matrix [CLIP | stats] (float64), CLIP width; checked like training input."""
    features = ImageFeatures.load(feature_dir, dataset, Path(FEATURES).name)
    rows = dict(zip(features.images, range(len(features.images))))
    return rows, features.matrix, sum(c.startswith("clip_") for c in features.columns)


def fit_linear(diff: np.ndarray, y: np.ndarray, weight: np.ndarray, penalty: np.ndarray,
               max_iter: int = 500) -> np.ndarray:
    """Minimize sum(weight * logistic loss of diff . w) + 0.5 * sum(penalty * w^2)."""
    d, t = torch.from_numpy(diff), torch.from_numpy(y.astype(np.float64))
    wt, pen = torch.from_numpy(weight / weight.sum()), torch.from_numpy(penalty)
    w = torch.zeros(diff.shape[1], dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([w], lr=1.0, max_iter=max_iter, tolerance_grad=1e-10,
                            tolerance_change=1e-12, history_size=20, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        loss = (wt * torch.nn.functional.binary_cross_entropy_with_logits(d @ w, t, reduction="none")).sum()
        loss = loss + 0.5 * (pen * w * w).sum()
        loss.backward()
        return loss

    opt.step(closure)
    out = w.detach().numpy().copy()
    if not np.isfinite(out).all():
        raise ValueError("non-finite weights")
    return out


def accuracy(diff_scores: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.where(diff_scores == 0, 0.5, (diff_scores > 0) == y.astype(bool))))


def standardize(x: np.ndarray, train: np.ndarray) -> np.ndarray:
    std = train.std(axis=0)
    return (x - train.mean(axis=0)) / np.where(std > 1e-12, std, 1.0)


def pca_basis(x: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    _, _, vt = np.linalg.svd(x - mean, full_matrices=False)
    vt = vt[:k]
    vt = vt * np.where(vt[np.arange(len(vt)), np.abs(vt).argmax(axis=1)] < 0, -1.0, 1.0)[:, None]  # fixed sign
    return mean, vt


def fold_of(group: str) -> int:
    return int(hashlib.sha256(f"{VERSION}:{group}".encode()).hexdigest(), 16) % FOLDS


def aux_pairs(raw_dir: Path, image_component: dict) -> pd.DataFrame:
    """Valid 4-image rankings of the non-preference TASTE criteria, as (image_a, image_b, a_wins)."""
    rankings = pd.read_parquet(raw_dir / "rankings.parquet")
    assets = pd.read_parquet(raw_dir / "assets.parquet").set_index("asset_id")["image_path"]
    rows = rankings[rankings["dimension"] != "preference"].assign(image=lambda d: d["asset_id"].map(assets))
    keys = ["dimension", "prompt_id", "evaluator_id"]
    ok = rows.groupby(keys).agg(n=("asset_id", "size"), assets=("asset_id", "nunique"),
                                images=("image", "nunique"),
                                ranks=("rank", lambda s: set(s) == {1, 2, 3, 4}))
    ok = ok[(ok["n"] == 4) & (ok["assets"] == 4) & (ok["images"] == 4) & ok["ranks"]].index
    rows = rows.set_index(keys).loc[lambda d: d.index.isin(ok)].reset_index()
    merged = rows.merge(rows, on=keys, suffixes=("_1", "_2"))
    merged = merged[merged["image_1"] < merged["image_2"]]
    out = pd.DataFrame({"image_a": merged["image_1"], "image_b": merged["image_2"],
                        "a_wins": (merged["rank_1"] < merged["rank_2"]).astype(int),
                        "dimension": merged["dimension"]})
    comp_a, comp_b = out["image_a"].map(image_component), out["image_b"].map(image_component)
    return out[comp_a.notna() & (comp_a == comp_b)].assign(component=comp_a).reset_index(drop=True)


def run_experiment(repo_root: Path) -> dict:
    feature_dir, split_dir = repo_root / FEATURES, repo_root / SPLITS
    t_rows, t_x, clip_dim = load_features(feature_dir, "taste")
    c_rows, c_x, _ = load_features(feature_dir, "creativeranking")

    # CreativeRanking model of step 9 (train pairs, own scaler), used as reference and prior.
    cr = pd.read_parquet(split_dir / "creativeranking.parquet")
    cr = cr[cr["split"] == "train"]
    ca, cb = cr["image_a"].map(c_rows).to_numpy(), cr["image_b"].map(c_rows).to_numpy()
    c_train = c_x[np.unique(np.concatenate([ca, cb]))]
    cz = standardize(c_x, c_train)
    w_cr = fit_linear(cz[ca] - cz[cb], cr["a_wins"].to_numpy(), np.ones(len(cr)), np.full(c_x.shape[1], CR_L2))
    s_cr = standardize(t_x, c_train) @ w_cr  # CR score of every TASTE image

    taste = pd.read_parquet(split_dir / "taste.parquet")
    taste = taste[taste["split"].isin(["train", "val"])].reset_index(drop=True)  # test never read
    image_component = {**dict(zip(taste["image_a"], taste["split_group"])),
                       **dict(zip(taste["image_b"], taste["split_group"]))}
    pa, pb = taste["image_a"].map(t_rows).to_numpy(), taste["image_b"].map(t_rows).to_numpy()
    py, pfold = taste["a_wins"].to_numpy(), taste["split_group"].map(fold_of).to_numpy()
    aux = aux_pairs(repo_root / "data/raw/taste", image_component)
    aux = aux[aux["image_a"].isin(t_rows) & aux["image_b"].isin(t_rows)]
    xa, xb = aux["image_a"].map(t_rows).to_numpy(), aux["image_b"].map(t_rows).to_numpy()
    xy, xfold = aux["a_wins"].to_numpy(), aux["component"].map(fold_of).to_numpy()

    results: dict[str, list] = {}

    def record(method: str, param, fold: int, acc: float, n: int) -> None:
        results.setdefault(f"{method}|{param}", []).append({"fold": fold, "accuracy": acc, "pairs": n})

    for k in range(FOLDS):
        tr, te = pfold != k, pfold == k
        train_rows = np.unique(np.concatenate([pa[tr], pb[tr]]))
        y_tr, y_te, n_te = py[tr], py[te], int(te.sum())
        record("cr_only", "-", k, accuracy(s_cr[pa[te]] - s_cr[pb[te]], y_te), n_te)

        z = standardize(t_x, t_x[train_rows])
        stats_cols = slice(clip_dim, t_x.shape[1])
        clip = t_x[:, :clip_dim]
        designs = {"full": z, "stats_only": z[:, stats_cols]}
        for dim in PCA_DIMS:
            mean, vt = pca_basis(clip[train_rows], dim)
            reduced = np.concatenate([(clip - mean) @ vt.T, t_x[:, stats_cols]], axis=1)
            designs[f"pca{dim}"] = standardize(reduced, reduced[train_rows])
        for name, m in designs.items():
            method = "pca" if name.startswith("pca") else name
            for l2 in L2_GRID:
                w = fit_linear(m[pa[tr]] - m[pb[tr]], y_tr, np.ones(int(tr.sum())), np.full(m.shape[1], l2))
                param = f"{name}, l2={l2}" if method == "pca" else f"l2={l2}"
                record(method, param, k, accuracy((m[pa[te]] - m[pb[te]]) @ w, y_te), n_te)

        prior = np.concatenate([s_cr[:, None], z], axis=1)
        for l2 in L2_GRID:
            penalty = np.concatenate([[0.0], np.full(z.shape[1], l2)])  # the CR score itself is not penalized
            w = fit_linear(prior[pa[tr]] - prior[pb[tr]], y_tr, np.ones(int(tr.sum())), penalty)
            record("cr_prior", f"l2={l2}", k, accuracy((prior[pa[te]] - prior[pb[te]]) @ w, y_te), n_te)

        aux_tr = xfold != k
        if aux_tr.any():
            diff = np.concatenate([z[pa[tr]] - z[pb[tr]], z[xa[aux_tr]] - z[xb[aux_tr]]])
            y_all = np.concatenate([y_tr, xy[aux_tr]])
            weight = np.concatenate([np.full(int(tr.sum()), 0.5 / tr.sum()),
                                     np.full(int(aux_tr.sum()), 0.5 / aux_tr.sum())])
            for l2 in L2_GRID:
                w = fit_linear(diff, y_all, weight, np.full(z.shape[1], l2))
                record("aux_dimensions", f"l2={l2}", k, accuracy((z[pa[te]] - z[pb[te]]) @ w, y_te), n_te)
        print(f"fold {k + 1}/{FOLDS} done ({n_te} held-out votes)", flush=True)

    summary = {}
    reference = {r["fold"]: r["accuracy"] for r in results["cr_only|-"]}
    for key, folds in results.items():
        accs = np.array([f["accuracy"] for f in folds])
        pairs = np.array([f["pairs"] for f in folds])
        gain = accs - np.array([reference[f["fold"]] for f in folds])
        summary[key] = {"cv_accuracy": float((accs * pairs).sum() / pairs.sum()),
                        "fold_std": float(accs.std(ddof=1)),
                        "gain_vs_cr_only": float(gain.mean()),
                        "gain_se": float(gain.std(ddof=1) / np.sqrt(len(gain)))}
    best = {}
    for key, s in summary.items():
        method = key.split("|")[0]
        if method not in best or s["cv_accuracy"] > summary[best[method]]["cv_accuracy"]:
            best[method] = key
    return {"summary": summary, "best_per_method": {m: {"setting": k.split("|")[1], **summary[k]}
                                                   for m, k in best.items()},
            "folds": FOLDS, "taste_votes": int(len(taste)), "aux_votes": int(len(aux)),
            "aux_dimensions": sorted(aux["dimension"].unique().tolist())}


def main(argv: list[str] | None = None, repo_root: Path = REPO_ROOT) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    result = run_experiment(repo_root)
    print(f"{'method':16s} {'best setting':22s} {'CV acc':>7s} {'fold sd':>8s} {'gain vs cr_only':>18s}")
    for method, b in sorted(result["best_per_method"].items(), key=lambda kv: -kv[1]["cv_accuracy"]):
        print(f"{method:16s} {b['setting']:22s} {b['cv_accuracy']:7.4f} {b['fold_std']:8.4f} "
              f"{b['gain_vs_cr_only']:+9.4f} ± {b['gain_se']:.4f}")
    inputs = {"taste_split_pairs": repo_root / SPLITS / "taste.parquet",
              "creativeranking_split_pairs": repo_root / SPLITS / "creativeranking.parquet",
              "feature_manifest": repo_root / FEATURES / "manifest.json",
              "taste_rankings": repo_root / "data/raw/taste/rankings.parquet"}
    report = {"version": VERSION, "evaluated_on": "5-fold CV over TASTE train+val groups (test never read)",
              **result, "code": code_revision(repo_root), "inputs": describe_inputs(inputs, repo_root),
              "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with staged_output(repo_root / "data/evaluation" / VERSION) as tmp:
        (tmp / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote data/evaluation/{VERSION}/results.json")
    return report


if __name__ == "__main__":
    main()
