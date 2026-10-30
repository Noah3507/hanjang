"""Tests for the TASTE follow-up check (step 9-7). Synthetic data only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_taste_followup.py"
spec = importlib.util.spec_from_file_location("ml_taste_followup", SCRIPT)
fu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fu)

DIM = 6
STATS = ["brightness", "contrast", "saturation", "n_colors"]


def _write(root: Path, n_groups=30, seed=0):
    rng = np.random.default_rng(seed)
    feature_dir, split_dir = root / fu.FEATURES, root / fu.SPLITS
    feature_dir.mkdir(parents=True)
    split_dir.mkdir(parents=True)
    true_w = rng.normal(size=DIM + 4)

    def features(ds, names, splits):
        clip, stats = rng.normal(size=(len(names), DIM)), rng.random((len(names), 4))
        pd.DataFrame({"row": range(len(names)), "image": names, "split": splits}).to_parquet(
            feature_dir / f"{ds}_index.parquet")
        np.save(feature_dir / f"{ds}_clip.npy", clip.astype(np.float32))
        np.save(feature_dir / f"{ds}_stats.npy", stats.astype(np.float32))
        return np.concatenate([clip, stats], axis=1)

    names = [f"images/{g}_{i}.png" for g in range(n_groups) for i in range(4)]
    split_of = lambda g: "train" if g < n_groups - 6 else "val"  # noqa: E731
    x = features("taste", names, [split_of(g) for g in range(n_groups) for _ in range(4)])
    rows = []
    for g in range(n_groups):
        imgs = list(range(4 * g, 4 * g + 4))
        for _ in range(2):
            for a in range(4):
                for b in range(a + 1, 4):
                    ia, ib = imgs[a], imgs[b]
                    rows.append((names[ia], names[ib], int((x[ia] - x[ib]) @ true_w > 0), split_of(g), f"comp{g}"))
    rows.append(("images/missing_a.png", "images/missing_b.png", 1, "test", "compT"))  # must never be read
    pd.DataFrame(rows, columns=["image_a", "image_b", "a_wins", "split", "split_group"]).to_parquet(
        split_dir / "taste.parquet")

    cr_names = [f"cr_{i}.png" for i in range(100)]
    cr_split = ["train" if i < 80 else "val" for i in range(100)]
    cx = features("creativeranking", cr_names, cr_split)
    cr_rows = [(cr_names[i], cr_names[i + 1], int((cx[i] - cx[i + 1]) @ true_w > 0), cr_split[i])
               for i in range(99) if cr_split[i] == cr_split[i + 1]]
    pd.DataFrame(cr_rows, columns=["image_a", "image_b", "a_wins", "split"]).to_parquet(
        split_dir / "creativeranking.parquet")
    (feature_dir / "manifest.json").write_text(json.dumps({
        "feature_version": Path(fu.FEATURES).name, "clip": {"embedding_dim": DIM}, "stats": {"columns": STATS}}))


def test_inner_folds_only_use_training_groups_and_are_deterministic():
    groups = np.array([f"comp{i}" for i in range(100)])
    outer = np.array([fu.fold_of(g, fu.OUTER_SALT, fu.FOLDS) for g in groups])
    inner = np.array([fu.fold_of(g, fu.VERSION + "-inner", fu.INNER_FOLDS) for g in groups[outer != 0]])
    assert set(inner) == set(range(fu.INNER_FOLDS))
    assert fu.fold_of("comp1", fu.OUTER_SALT, fu.FOLDS) == fu.fold_of("comp1", fu.OUTER_SALT, fu.FOLDS)


def test_choose_l2_prefers_the_larger_value_on_ties(monkeypatch):
    monkeypatch.setattr(fu, "L2_GRID", [1.0, 10.0])
    x = np.zeros((8, 3))  # no information: every L2 gives the same accuracy
    ra, rb = np.array([0, 2, 4, 6]), np.array([1, 3, 5, 7])
    best, result = fu.choose_l2(x, ra, rb, np.array([1, 0, 1, 0]), np.array(["a", "b", "c", "d"]))
    assert result[1.0] == result[10.0] and best == 10.0


def test_followup_reports_all_parts_and_never_reads_test(tmp_path):
    _write(tmp_path)
    result = fu.run(tmp_path)
    assert result["taste_votes"] == 30 * 12  # the test row is not counted
    assert set(result["flat_cv"]) == {str(l2) for l2 in fu.L2_GRID}
    assert len(result["nested_cv"]["chosen_l2_per_fold"]) == fu.FOLDS
    assert result["nested_cv"]["cv_accuracy"] > 0.7
    assert [c["alpha"] for c in result["combination"]] == fu.ALPHAS
    assert set(result["decisions"]) == {"taste_secondary_signal", "combine_scores"}


def test_alpha_zero_is_the_creativeranking_model(tmp_path):
    _write(tmp_path)
    result = fu.run(tmp_path)
    zero = result["combination"][0]
    assert zero["alpha"] == 0.0
    assert zero["creativeranking_val_accuracy"] == pytest.approx(result["creativeranking_val"]["cr_model_accuracy"])
    assert zero["taste_cv_accuracy"] == pytest.approx(result["cr_only_cv_accuracy"])


def test_followup_is_deterministic_and_writes_results(tmp_path):
    _write(tmp_path)
    first = fu.main([], repo_root=tmp_path)
    second = fu.main([], repo_root=tmp_path)
    assert first["nested_cv"] == second["nested_cv"] and first["combination"] == second["combination"]
    assert (tmp_path / "data/evaluation/taste-followup-v1/results.json").exists()
