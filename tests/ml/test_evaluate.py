"""End-to-end tests for the TASTE model training and the one-time test evaluation. Synthetic data only."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from safetensors.numpy import save_file

from ml.training.bt_logistic import load_model

ROOT = Path(__file__).resolve().parents[2]
VERSION = "ViT-B-32-openai-qg-pad-square-v1-stats-v1"
STATS = ["brightness", "contrast", "saturation", "n_colors"]
DIM = 6


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, seed=0):
    rng = np.random.default_rng(seed)
    feature_dir = root / "data/features" / VERSION
    split_dir = root / "data/processed/splits/split-v1"
    feature_dir.mkdir(parents=True)
    split_dir.mkdir(parents=True)
    true_w = rng.normal(size=DIM + 4)
    columns = [f"clip_{i}" for i in range(DIM)] + STATS

    def features(ds, names, splits):
        clip, stats = rng.normal(size=(len(names), DIM)), rng.random((len(names), 4))
        pd.DataFrame({"row": range(len(names)), "image": names, "split": splits}).to_parquet(
            feature_dir / f"{ds}_index.parquet")
        np.save(feature_dir / f"{ds}_clip.npy", clip.astype(np.float32))
        np.save(feature_dir / f"{ds}_stats.npy", stats.astype(np.float32))
        keep = [i for i, s in enumerate(splits) if s in ("val", "test")]
        pd.DataFrame({"row": range(len(keep)), "image": [names[i] for i in keep],
                      "split": [splits[i] for i in keep]}).to_parquet(feature_dir / f"{ds}_center_crop_index.parquet")
        crop = clip[keep] + 0.3 * rng.normal(size=(len(keep), DIM))
        np.save(feature_dir / f"{ds}_clip_center_crop.npy", crop.astype(np.float32))
        return np.concatenate([clip, stats], axis=1)

    # TASTE: 40 prompts of 4 images, 2 votes each; prompts 0-27 train, 28-33 val, 34-39 test
    split_of = lambda g: "train" if g < 28 else ("val" if g < 34 else "test")  # noqa: E731
    names = [f"images/{g}_{i}.png" for g in range(40) for i in range(4)]
    x = features("taste", names, [split_of(g) for g in range(40) for _ in range(4)])
    rows = []
    for g in range(40):
        imgs = list(range(4 * g, 4 * g + 4))
        for vote in range(2):
            for a in range(4):
                for b in range(a + 1, 4):
                    ia, ib = imgs[a], imgs[b]
                    win = int((x[ia] - x[ib]) @ true_w + 0.3 * rng.normal() > 0)
                    rows.append((names[ia], names[ib], win, g, f"e{vote}", f"taste:{g}", split_of(g), f"comp{g}"))
    pd.DataFrame(rows, columns=["image_a", "image_b", "a_wins", "prompt_id", "evaluator_id", "group_id", "split",
                                "split_group"]).to_parquet(split_dir / "taste.parquet")

    # CreativeRanking: 30 products of 3 images; products 0-19 train, 20-24 val, 25-29 test
    cr_split = lambda p: "train" if p < 20 else ("val" if p < 25 else "test")  # noqa: E731
    cr_names = [f"cr_{p}_{i}.png" for p in range(30) for i in range(3)]
    cx = features("creativeranking", cr_names, [cr_split(p) for p in range(30) for _ in range(3)])
    ctr = 0.05 + 0.02 * np.tanh(cx @ true_w)
    cr_rows = []
    for p in range(30):
        for a in range(3):
            for b in range(a + 1, 3):
                ia, ib = 3 * p + a, 3 * p + b
                cr_rows.append((f"cr:p{p}", cr_names[ia], cr_names[ib], int(ctr[ia] > ctr[ib]), 1000,
                                int(1000 * ctr[ia]), 1000, int(1000 * ctr[ib]), cr_split(p), f"cr:p{p}"))
    pd.DataFrame(cr_rows, columns=["group_id", "image_a", "image_b", "a_wins", "pv_a", "clk_a", "pv_b", "clk_b",
                                   "split", "split_group"]).to_parquet(split_dir / "creativeranking.parquet")
    (feature_dir / "manifest.json").write_text(json.dumps({
        "feature_version": VERSION, "clip": {"embedding_dim": DIM}, "stats": {"columns": STATS}}))

    # a stand-in for the step 9 CreativeRanking model (weights near the true direction)
    out = root / "artifacts/models/ranking/bt-logistic-v1"
    out.mkdir(parents=True)
    save_file({"weights": true_w + 0.1 * rng.normal(size=DIM + 4), "scaler_mean": np.zeros(DIM + 4),
               "scaler_std": np.ones(DIM + 4)}, str(out / "model.safetensors"))
    (out / "model_config.json").write_text(json.dumps({
        "model_version": "bt-logistic-v1", "feature_version": VERSION, "feature_columns": columns}))
    config = json.loads((ROOT / "ml/training/taste_config.json").read_text())
    (root / "taste_config.json").write_text(json.dumps(config))
    _record_step8(root)


def _record_step8(root: Path, override: dict | None = None):
    """Write the step 8 record the way scripts/ml_baselines.py names the rule."""
    from ml.training.bt_logistic import ImageFeatures

    evaluate = _load("ml_evaluate")
    datasets = {}
    for ds in ("creativeranking", "taste"):
        features = ImageFeatures.load(root / "data/features" / VERSION, ds, VERSION)
        pairs = pd.read_parquet(root / "data/processed/splits/split-v1" / f"{ds}.parquet")
        rule = (override or {}).get(ds) or evaluate.train_rule(pairs[pairs["split"] == "train"], features)
        datasets[ds] = {"accuracy": {"random": 0.5, f"rule ({rule}, chosen on train)": 0.55}}
    path = root / "data/evaluation/baselines-v1/results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"datasets": datasets}))


def test_taste_model_is_trained_on_train_and_val_only(tmp_path):
    _write(tmp_path)
    report = _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    assert report["train_votes"] == 34 * 12  # train + val prompts, never the 6 test prompts
    config, scaler, weights = load_model(tmp_path / "artifacts/models/ranking/bt-taste-v1")
    assert config["trained_on_splits"] == ["train", "val"] and config["l2"] == 30.0
    assert weights.shape == (DIM + 4,) and config["feature_columns"][-4:] == STATS


def test_taste_config_refuses_the_test_split(tmp_path):
    _write(tmp_path)
    config = json.loads((tmp_path / "taste_config.json").read_text())
    config["train_splits"] = ["train", "test"]
    (tmp_path / "taste_config.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="test split"):
        _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)


def test_evaluation_reports_everything_once(tmp_path):
    _write(tmp_path)
    _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    evaluate = _load("ml_evaluate")
    report = evaluate.main(["--skip-laion"], repo_root=tmp_path)
    cr, taste = report["datasets"]["creativeranking"], report["datasets"]["taste"]
    assert cr["pairs"] == 5 * 3 and taste["pairs"] == 6 * 12  # test pairs only
    primary = cr["models"]["creativeranking_model"]
    assert primary["accuracy"]["mean"] > 0.7 and primary["accuracy"]["groups"] == 5 == cr["clusters"]
    assert primary["ranking"]["groups"] == 5
    assert set(primary["center_crop_sensitivity"]) == {"note", "accuracy", "padding_minus_center_crop"}
    assert set(primary["difference_vs_baselines"]) == {"random", "rule"}
    assert set(taste["models"]) == {"creativeranking_model", "taste_model"}
    assert 0.5 <= taste["designer_agreement_reference"] <= 1.0
    assert set(taste["baselines"]) == {"random", "rule"}
    assert set(cr["decision"]) == {"creativeranking_model"} and set(taste["decision"]) == {"taste_model"}
    assert len(report["creativeranking_val_score_gaps"]) == 5
    with pytest.raises(SystemExit, match="only once"):
        evaluate.main(["--skip-laion"], repo_root=tmp_path)
    with pytest.raises(SystemExit, match="only once"):
        evaluate.main(["--skip-laion", "--check-only"], repo_root=tmp_path)


def test_evaluation_refuses_a_model_with_other_feature_columns(tmp_path):
    _write(tmp_path)
    _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    path = tmp_path / "artifacts/models/ranking/bt-logistic-v1/model_config.json"
    config = json.loads(path.read_text())
    config["feature_columns"] = config["feature_columns"][::-1]
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="column order"):
        _load("ml_evaluate").main(["--skip-laion"], repo_root=tmp_path)
    assert not (tmp_path / "data/evaluation/final-test-v1").exists()


def test_load_model_rejects_wrong_shapes(tmp_path):
    out = tmp_path / "m"
    out.mkdir()
    save_file({"weights": np.ones(3), "scaler_mean": np.zeros(3), "scaler_std": np.ones(3)}, str(out / "model.safetensors"))
    (out / "model_config.json").write_text(json.dumps({"feature_columns": ["a", "b"]}))
    with pytest.raises(ValueError, match="finite numbers"):
        load_model(out)


def test_check_only_reads_no_labels_and_writes_nothing(tmp_path, monkeypatch):
    _write(tmp_path)
    _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    evaluate = _load("ml_evaluate")
    real_read = pd.read_parquet
    asked = []

    def spy(path, *args, **kwargs):
        asked.append((kwargs.get("columns"), kwargs.get("filters")))
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(evaluate.pd, "read_parquet", spy)
    result = evaluate.main(["--skip-laion", "--check-only"], repo_root=tmp_path)
    split_reads = [(c, f) for c, f in asked if c is not None]
    assert split_reads
    # labels are read only together with a filter that keeps train rows (for the step 8 rule check)
    assert all("a_wins" not in c or f == [("split", "==", "train")] for c, f in split_reads)
    assert result["taste"]["test_pairs"] == 6 * 12 and result["taste"]["split_group_matches_components"] is True
    assert not (tmp_path / "data/evaluation/final-test-v1").exists()


def test_taste_groups_that_do_not_match_image_components_stop_the_run(tmp_path):
    _write(tmp_path)
    _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    path = tmp_path / "data/processed/splits/split-v1/taste.parquet"
    pairs = pd.read_parquet(path)
    test_rows = pairs.index[pairs["split"] == "test"]
    pairs.loc[test_rows[:3], "split_group"] = "comp-wrong"  # part of one component gets another group
    pairs.to_parquet(path)
    with pytest.raises(ValueError, match="split_group does not match"):
        _load("ml_evaluate").main(["--skip-laion", "--check-only"], repo_root=tmp_path)


def _ready(tmp_path):
    _write(tmp_path)
    _load("ml_train_taste").main(["--config", str(tmp_path / "taste_config.json")], repo_root=tmp_path)
    return _load("ml_evaluate"), tmp_path / "data/evaluation"


def test_a_rule_that_differs_from_the_step8_record_stops_the_run(tmp_path):
    evaluate, _ = _ready(tmp_path)
    actual = evaluate.step8_rules(tmp_path / evaluate.STEP8)["taste"]  # written from the same train choice
    other = "brightness-" if actual != "brightness-" else "brightness+"
    _record_step8(tmp_path, {"taste": other})
    with pytest.raises(ValueError, match="step 8 record"):
        evaluate.main(["--skip-laion", "--check-only"], repo_root=tmp_path)


def test_an_error_during_the_evaluation_leaves_no_results(tmp_path, monkeypatch):
    evaluate, out = _ready(tmp_path)
    monkeypatch.setattr(evaluate, "evaluate_dataset", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        evaluate.main(["--skip-laion"], repo_root=tmp_path)
    assert sorted(p.name for p in out.iterdir()) == ["baselines-v1"]  # no results, no hidden temporary folder


def test_an_error_while_writing_leaves_no_results(tmp_path, monkeypatch):
    evaluate, out = _ready(tmp_path)
    real = Path.write_text

    def failing(self, *args, **kwargs):
        if self.name == "results.json.sha256":
            raise OSError("disk full")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing)
    with pytest.raises(OSError):
        evaluate.main(["--skip-laion"], repo_root=tmp_path)
    assert sorted(p.name for p in out.iterdir()) == ["baselines-v1"]


def test_saved_results_survive_a_printing_error_and_block_a_rerun(tmp_path, monkeypatch):
    import hashlib

    evaluate, out = _ready(tmp_path)
    monkeypatch.setattr(evaluate, "print_summary", lambda report: (_ for _ in ()).throw(RuntimeError("print")))
    with pytest.raises(RuntimeError):
        evaluate.main(["--skip-laion"], repo_root=tmp_path)
    folder = out / "final-test-v1"
    digest = hashlib.sha256((folder / "results.json").read_bytes()).hexdigest()
    assert (folder / "results.json.sha256").read_text() == f"{digest}  results.json\n"
    with pytest.raises(SystemExit, match="only once"):
        evaluate.main(["--skip-laion"], repo_root=tmp_path)
