"""Tests for the TASTE remedy experiment (step 9-6). Synthetic data only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_taste_experiment.py"
spec = importlib.util.spec_from_file_location("ml_taste_experiment", SCRIPT)
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)

DIM = 6


def _write(root: Path, n_groups=30, seed=0):
    rng = np.random.default_rng(seed)
    feature_dir = root / exp.FEATURES
    split_dir = root / exp.SPLITS
    raw = root / "data/raw/taste"
    for d in (feature_dir, split_dir, raw):
        d.mkdir(parents=True)
    true_w = rng.normal(size=DIM + 4)

    def features(ds, names, splits):
        clip, stats = rng.normal(size=(len(names), DIM)), rng.random((len(names), 4))
        pd.DataFrame({"row": range(len(names)), "image": names, "split": splits}).to_parquet(
            feature_dir / f"{ds}_index.parquet")
        np.save(feature_dir / f"{ds}_clip.npy", clip.astype(np.float32))
        np.save(feature_dir / f"{ds}_stats.npy", stats.astype(np.float32))
        return np.concatenate([clip, stats], axis=1)

    names = [f"images/{g}_{i}.png" for g in range(n_groups) for i in range(4)]
    x = features("taste", names, ["train" if g < n_groups - 6 else "val" for g in range(n_groups) for _ in range(4)])
    rows, ranking_rows, assets = [], [], []
    for g in range(n_groups):
        imgs = list(range(4 * g, 4 * g + 4))
        split = "train" if g < n_groups - 6 else "val"
        for i in imgs:
            assets.append((i, names[i]))
        for vote in range(2):
            for a in range(4):
                for b in range(a + 1, 4):
                    ia, ib = imgs[a], imgs[b]
                    rows.append((names[ia], names[ib], int((x[ia] - x[ib]) @ true_w > 0), split, f"comp{g}"))
            order = np.argsort(-(x[imgs] @ true_w))
            for rank, pos in enumerate(order, start=1):
                ranking_rows.append(("color_harmony", g, imgs[pos], f"e{vote}", rank))
    rows.append(("images/missing_a.png", "images/missing_b.png", 1, "test", "compT"))  # must never be read
    pd.DataFrame(rows, columns=["image_a", "image_b", "a_wins", "split", "split_group"]).to_parquet(
        split_dir / "taste.parquet")
    pd.DataFrame(ranking_rows, columns=["dimension", "prompt_id", "asset_id", "evaluator_id", "rank"]).to_parquet(
        raw / "rankings.parquet")
    pd.DataFrame(assets, columns=["asset_id", "image_path"]).to_parquet(raw / "assets.parquet")

    cr_names = [f"cr_{i}.png" for i in range(80)]
    cx = features("creativeranking", cr_names, ["train"] * len(cr_names))
    cr_rows = [(cr_names[i], cr_names[i + 1], int((cx[i] - cx[i + 1]) @ true_w > 0), "train")
               for i in range(0, 79)]
    pd.DataFrame(cr_rows, columns=["image_a", "image_b", "a_wins", "split"]).to_parquet(
        split_dir / "creativeranking.parquet")
    (feature_dir / "manifest.json").write_text(json.dumps({
        "feature_version": Path(exp.FEATURES).name, "clip": {"embedding_dim": DIM},
        "stats": {"columns": ["brightness", "contrast", "saturation", "n_colors"]}}))


def test_fit_leaves_an_unpenalized_column_free():
    rng = np.random.default_rng(0)
    diff = rng.normal(size=(300, 2))
    y = (diff[:, 0] > 0).astype(float)
    w = exp.fit_linear(diff, y, np.ones(300), np.array([0.0, 100.0]))
    assert abs(w[0]) > 10 * abs(w[1])


def test_accuracy_counts_zero_difference_as_half():
    assert exp.accuracy(np.array([1.0, -1.0, 0.0]), np.array([1, 1, 0])) == pytest.approx(0.5)


def test_fold_assignment_is_deterministic_and_covers_all_folds():
    folds = [exp.fold_of(f"comp{i}") for i in range(200)]
    assert folds == [exp.fold_of(f"comp{i}") for i in range(200)]
    assert set(folds) == set(range(exp.FOLDS))


def test_pca_basis_has_a_fixed_sign():
    x = np.random.default_rng(1).normal(size=(50, 6))
    _, vt1 = exp.pca_basis(x, 3)
    _, vt2 = exp.pca_basis(x.copy(), 3)
    assert np.allclose(vt1, vt2)


def test_aux_pairs_keep_only_valid_rankings_inside_one_component(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame({"asset_id": range(8), "image_path": [f"i{k}.png" for k in range(8)]}).to_parquet(
        raw / "assets.parquet")
    rows = [("typography", 1, a, "e1", r) for a, r in zip([0, 1, 2, 3], [1, 2, 3, 4])]     # valid
    rows += [("typography", 2, a, "e1", r) for a, r in zip([4, 5, 6, 7], [1, 1, 3, 4])]    # tied ranks
    rows += [("preference", 3, a, "e1", r) for a, r in zip([0, 1, 2, 3], [1, 2, 3, 4])]    # target, excluded
    pd.DataFrame(rows, columns=["dimension", "prompt_id", "asset_id", "evaluator_id", "rank"]).to_parquet(
        raw / "rankings.parquet")
    component = {"i0.png": "c1", "i1.png": "c1", "i2.png": "c1", "i3.png": "c2"}
    pairs = exp.aux_pairs(raw, component)
    assert len(pairs) == 3  # the 3 pairs among i0, i1, i2; pairs touching i3 cross components
    assert set(pairs["dimension"]) == {"typography"}


def test_experiment_compares_all_methods_and_never_reads_test(tmp_path):
    _write(tmp_path)
    result = exp.run_experiment(tmp_path)
    assert set(result["best_per_method"]) == {"cr_only", "full", "stats_only", "pca", "cr_prior", "aux_dimensions"}
    for summary in result["summary"].values():
        assert 0.0 <= summary["cv_accuracy"] <= 1.0
    assert result["taste_votes"] == 30 * 12  # the test row is not counted
    assert result["best_per_method"]["full"]["cv_accuracy"] > 0.7


def test_experiment_is_deterministic_and_writes_results(tmp_path):
    _write(tmp_path)
    first = exp.main([], repo_root=tmp_path)
    second = exp.main([], repo_root=tmp_path)
    assert first["summary"] == second["summary"]
    assert (tmp_path / "data/evaluation/taste-experiment-v1/results.json").exists()


def test_damaged_feature_cache_stops_the_experiment(tmp_path):
    _write(tmp_path)
    path = tmp_path / exp.FEATURES / "taste_clip.npy"
    clip = np.load(path)
    clip[0, 0] = np.nan
    np.save(path, clip)
    with pytest.raises(ValueError, match="NaN or infinite"):
        exp.run_experiment(tmp_path)
