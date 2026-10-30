"""Tests for the baselines. Synthetic features only, nothing is downloaded."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from ml.evaluation.baselines import (
    FeatureCache,
    load_laion_linear,
    pairwise_accuracy,
    random_accuracy,
    rule_accuracies,
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_baselines.py"
NAMES = ["brightness", "contrast", "saturation", "n_colors"]


def test_pairwise_accuracy_counts_ties_as_half():
    assert pairwise_accuracy([2, 1, 5], [1, 2, 5], [1, 1, 0]) == pytest.approx((1 + 0 + 0.5) / 3)
    with pytest.raises(ValueError):
        pairwise_accuracy([], [], [])


def test_random_baseline_is_seeded_and_near_half():
    labels = np.random.default_rng(1).random(20_000) < 0.5
    first = random_accuracy(labels, seed=0)
    assert first == random_accuracy(labels, seed=0)
    assert abs(first - 0.5) < 0.02


def test_rule_accuracies_cover_both_directions():
    stats_a = np.array([[0.9, 0, 0, 0], [0.8, 0, 0, 0]])
    stats_b = np.array([[0.1, 0, 0, 0], [0.2, 0, 0, 0]])
    result = rule_accuracies(stats_a, stats_b, np.array([1, 1]), NAMES)
    assert result["brightness+"] == 1.0 and result["brightness-"] == 0.0
    assert result["contrast+"] == 0.5  # all ties


def test_laion_weights_load_safely_and_check_shape(tmp_path):
    path = tmp_path / "head.pth"
    torch.save({"weight": torch.ones(1, 8), "bias": torch.tensor([0.5])}, path)
    weight, bias = load_laion_linear(path, 8)
    assert weight.shape == (8,) and bias == 0.5
    with pytest.raises(ValueError):
        load_laion_linear(path, 512)


def _write_cache(root: Path, n_images=40, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    features = root / "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"
    split_dir = root / "data/processed/splits/split-v1"
    features.mkdir(parents=True)
    split_dir.mkdir(parents=True)
    (features / "manifest.json").write_text(json.dumps({"stats": {"columns": NAMES}}))
    for ds in ("taste", "creativeranking"):
        images = [f"{ds}_{i}.png" for i in range(n_images)]
        stats = rng.random((n_images, 4)).astype(np.float32)
        clip = rng.normal(size=(n_images, dim)).astype(np.float32)
        pd.DataFrame({"row": range(n_images), "image": images, "split": "train", "had_alpha": False}).to_parquet(
            features / f"{ds}_index.parquet")
        np.save(features / f"{ds}_clip.npy", clip)
        np.save(features / f"{ds}_stats.npy", stats)
        rows = []
        for k in range(0, n_images, 2):
            split = "train" if k < n_images * 0.6 else "val"
            # the brighter image always wins, so the brightness+ rule should be picked
            rows.append((images[k], images[k + 1], split, int(stats[k, 0] > stats[k + 1, 0])))
        pd.DataFrame(rows, columns=["image_a", "image_b", "split", "a_wins"]).to_parquet(split_dir / f"{ds}.parquet")
    laion = root / "data/raw/laion"
    laion.mkdir(parents=True)
    torch.save({"weight": torch.ones(1, dim), "bias": torch.tensor([0.0])}, laion / "sa_0_4_vit_b_32_linear.pth")


def _load_script():
    spec = importlib.util.spec_from_file_location("ml_baselines", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_scores_every_baseline_on_the_same_val_pairs(tmp_path):
    _write_cache(tmp_path)
    results = _load_script().main([], repo_root=tmp_path)
    for ds, result in results["datasets"].items():
        assert set(result["accuracy"]) == {"random", "rule (brightness+, chosen on train)", "laion_aesthetic"}
        assert result["accuracy"]["rule (brightness+, chosen on train)"] == 1.0
        assert result["val_pairs"] == 8 and result["train_pairs"] == 12
    saved = json.loads((tmp_path / "data/evaluation/baselines-v1/results.json").read_text())
    assert saved["evaluated_on"] == "val" and set(saved["code"]) == {"commit", "dirty"}


def test_missing_laion_weights_is_a_clear_error_unless_skipped(tmp_path):
    _write_cache(tmp_path)
    (tmp_path / "data/raw/laion/sa_0_4_vit_b_32_linear.pth").unlink()
    with pytest.raises(SystemExit):
        _load_script().main([], repo_root=tmp_path)
    results = _load_script().main(["--skip-laion"], repo_root=tmp_path)
    assert "laion_aesthetic" not in results["datasets"]["taste"]["accuracy"]


def test_pairs_without_cached_features_are_an_error(tmp_path):
    _write_cache(tmp_path)
    cache = FeatureCache.load(tmp_path / "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1", "taste")
    with pytest.raises(ValueError):
        cache.rows(pd.Series(["not_cached.png"]))
