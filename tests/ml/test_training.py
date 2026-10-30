"""Tests for the logistic Bradley-Terry model. Synthetic features only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from safetensors.numpy import load_file

from ml.training.bt_logistic import PairSet, Scaler, concat, fit_bt, pairwise_accuracy, scores

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_train.py"
STATS = ["brightness", "contrast", "saturation", "n_colors"]


def _pairs_from_true_weights(n=400, dim=6, seed=0):
    rng = np.random.default_rng(seed)
    true_w = rng.normal(size=dim)
    a, b = rng.normal(size=(n, dim)), rng.normal(size=(n, dim))
    y = ((a - b) @ true_w > 0).astype(float)
    return PairSet(a, b, y, np.full(n, 1 / n), np.full(n, "x")), true_w


def test_fit_recovers_the_preference_direction_and_is_deterministic():
    train, true_w = _pairs_from_true_weights()
    scaler = Scaler.fit(np.concatenate([train.a, train.b]))
    w1 = fit_bt(train, scaler, l2=1e-3)
    w2 = fit_bt(train, scaler, l2=1e-3)
    assert np.array_equal(w1, w2)
    cosine = (w1 * scaler.std) @ true_w / (np.linalg.norm(w1 * scaler.std) * np.linalg.norm(true_w))
    assert cosine > 0.95
    acc = pairwise_accuracy(scores(train.a, scaler, w1), scores(train.b, scaler, w1), train.y)
    assert acc > 0.95


def test_scores_are_antisymmetric_so_swapping_images_flips_the_probability():
    train, _ = _pairs_from_true_weights()
    scaler = Scaler.fit(np.concatenate([train.a, train.b]))
    w = fit_bt(train, scaler, l2=1e-2)
    d = scores(train.a, scaler, w) - scores(train.b, scaler, w)
    assert np.allclose(1 / (1 + np.exp(-d)) + 1 / (1 + np.exp(d)), 1.0)


def test_stronger_l2_gives_smaller_weights():
    train, _ = _pairs_from_true_weights()
    scaler = Scaler.fit(np.concatenate([train.a, train.b]))
    assert np.linalg.norm(fit_bt(train, scaler, l2=1.0)) < np.linalg.norm(fit_bt(train, scaler, l2=1e-4))


def test_joint_training_weights_each_dataset_equally():
    small, _ = _pairs_from_true_weights(n=10)
    big, _ = _pairs_from_true_weights(n=1000, seed=1)
    joint = concat([small, big])
    assert joint.weight.sum() == pytest.approx(1.0)
    assert joint.weight[:10].sum() == pytest.approx(0.5)


def test_constant_feature_does_not_break_the_scaler():
    x = np.array([[1.0, 5.0], [3.0, 5.0]])
    z = Scaler.fit(x).transform(x)
    assert np.isfinite(z).all() and (z[:, 1] == 0).all()


def _write_inputs(root: Path, n_images=60, dim=6, seed=0):
    rng = np.random.default_rng(seed)
    version = "ViT-B-32-openai-qg-pad-square-v1-stats-v1"
    feature_dir = root / "data/features" / version
    split_dir = root / "data/processed/splits/split-v1"
    feature_dir.mkdir(parents=True)
    split_dir.mkdir(parents=True)
    (feature_dir / "manifest.json").write_text(json.dumps({
        "feature_version": version, "clip": {"model": "ViT-B-32", "embedding_dim": dim}, "stats": {"columns": STATS}}))
    true_w = rng.normal(size=dim + 4)
    for ds in ("taste", "creativeranking"):
        images = [f"{ds}_{i}.png" for i in range(n_images)]
        clip, stats = rng.normal(size=(n_images, dim)), rng.random((n_images, 4))
        image_split = ["train" if i < 36 else ("val" if i < 48 else "test") for i in range(n_images)]
        pd.DataFrame({"row": range(n_images), "image": images, "split": image_split, "had_alpha": False}).to_parquet(
            feature_dir / f"{ds}_index.parquet")
        np.save(feature_dir / f"{ds}_clip.npy", clip.astype(np.float32))
        np.save(feature_dir / f"{ds}_stats.npy", stats.astype(np.float32))
        x = np.concatenate([clip, stats], axis=1)
        rows = []
        for i in range(n_images):
            for j in range(i + 1, min(i + 4, n_images)):
                split = "train" if i < 36 else ("val" if i < 48 else "test")
                if split == "test" or j >= 48 and split == "val" or j >= 36 and split == "train":
                    continue
                rows.append((images[i], images[j], split, int((x[i] - x[j]) @ true_w > 0)))
        pd.DataFrame(rows, columns=["image_a", "image_b", "split", "a_wins"]).to_parquet(split_dir / f"{ds}.parquet")
    config = {"version": "bt-test", "feature_version": version, "split_version": "split-v1",
              "training_sets": {"taste": ["taste"], "joint": ["taste", "creativeranking"]},
              "l2": [0.001, 0.1], "max_iter": 200,
              "selection": {"primary": "creativeranking", "secondary": "taste"}}
    (root / "config.json").write_text(json.dumps(config))


def _run(root: Path):
    spec = importlib.util.spec_from_file_location("ml_train", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(["--config", str(root / "config.json")], repo_root=root)


def test_script_writes_a_reloadable_model_and_never_reads_test(tmp_path):
    _write_inputs(tmp_path)
    report = _run(tmp_path)
    out = tmp_path / "artifacts/models/ranking/bt-test"
    tensors = load_file(str(out / "model.safetensors"))
    config = json.loads((out / "model_config.json").read_text())
    assert tensors["weights"].shape == (10,) and tensors["scaler_std"].shape == (10,)
    assert config["feature_columns"][-4:] == STATS and config["method"] == "bradley_terry_sigmoid_v1"
    assert len(report["runs"]) == 4 and report["chosen"]["mean_val_accuracy"] > 0.7
    assert report["evaluated_on"].startswith("val")
    assert all(set(r["val"]) == {"taste", "creativeranking"} for r in report["runs"])


def test_same_config_gives_the_same_model(tmp_path):
    _write_inputs(tmp_path)
    _run(tmp_path)
    first = load_file(str(tmp_path / "artifacts/models/ranking/bt-test/model.safetensors"))["weights"]
    _run(tmp_path)
    second = load_file(str(tmp_path / "artifacts/models/ranking/bt-test/model.safetensors"))["weights"]
    assert np.array_equal(first, second)


def _load_script():
    spec = importlib.util.spec_from_file_location("ml_train", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FEATURES = "data/features/ViT-B-32-openai-qg-pad-square-v1-stats-v1"


@pytest.mark.parametrize("damage", ["nan", "inf"])
def test_nan_or_infinite_features_stop_training(tmp_path, damage):
    _write_inputs(tmp_path)
    path = tmp_path / FEATURES / "taste_clip.npy"
    clip = np.load(path)
    clip[3, 2] = np.nan if damage == "nan" else np.inf
    np.save(path, clip)
    with pytest.raises(ValueError, match="NaN or infinite"):
        _run(tmp_path)
    assert not (tmp_path / "artifacts").exists()


def test_feature_version_mismatch_stops_training(tmp_path):
    _write_inputs(tmp_path)
    manifest = tmp_path / FEATURES / "manifest.json"
    data = json.loads(manifest.read_text())
    data["feature_version"] = "ViT-B-32-openai-gelu-pad-square-v1-stats-v1"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="config expects"):
        _run(tmp_path)


def test_wrong_feature_width_or_column_order_stops_training(tmp_path):
    _write_inputs(tmp_path)
    manifest = tmp_path / FEATURES / "manifest.json"
    data = json.loads(manifest.read_text())
    data["clip"]["embedding_dim"] = 512
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="embedding_dim"):
        _run(tmp_path)

    _write_inputs(tmp_path / "order")
    stats = tmp_path / "order" / FEATURES / "creativeranking_stats.npy"
    np.save(stats, np.load(stats)[:, :3])  # one stats column missing in one dataset
    with pytest.raises(ValueError, match="stats width"):
        _run(tmp_path / "order")


def test_pair_image_in_another_split_stops_training(tmp_path):
    _write_inputs(tmp_path)
    index_path = tmp_path / FEATURES / "taste_index.parquet"
    index = pd.read_parquet(index_path)
    index.loc[0, "split"] = "val"  # image 0 is used by train pairs
    index.to_parquet(index_path)
    with pytest.raises(ValueError, match="another split"):
        _run(tmp_path)


def test_selection_uses_creativeranking_first_then_taste_then_larger_l2():
    choose = _load_script().choose_best
    run = lambda name, l2, cr, taste: {"training_set": name, "l2": l2,  # noqa: E731
                                       "val": {"creativeranking": {"accuracy": cr}, "taste": {"accuracy": taste}}}
    rule = {"primary": "creativeranking", "secondary": "taste"}
    runs = [run("a", 0.01, 0.66, 0.60), run("b", 0.01, 0.68, 0.50), run("c", 0.1, 0.68, 0.50)]
    assert choose(runs, rule)["training_set"] == "c"  # a has the best mean but lower CR accuracy
    runs.append(run("d", 0.001, 0.68, 0.52))
    assert choose(runs, rule)["training_set"] == "d"
