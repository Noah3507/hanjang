"""Tests for train/val/test assignment and leakage checks. Synthetic data only."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from ml.data.split import (
    assign_by_hash,
    check_no_leakage,
    image_components,
    leakage_report,
    load_config,
    split_creativeranking,
    split_taste,
)

CONFIG = Path(__file__).resolve().parents[2] / "ml" / "data" / "split_config.json"
FRACTIONS = {"train": 0.7, "val": 0.15, "test": 0.15}


def taste_pairs(n_groups=20, shared=None):
    """Each prompt group compares 4 own images; `shared` links two groups by one image."""
    rows = []
    for g in range(n_groups):
        images = [f"img{g}_{k}.png" for k in range(4)]
        if shared and g == shared[1]:
            images[0] = f"img{shared[0]}_0.png"  # reuse an image of another group
        for i in range(4):
            for j in range(i + 1, 4):
                a, b = sorted((images[i], images[j]))
                rows.append(("taste", None, f"taste:{g}", a, b, 1))
    return pd.DataFrame(rows, columns=["dataset", "source_split", "group_id", "image_a", "image_b", "a_wins"])


def cr_pairs():
    rows = [
        ("creativeranking", "train", "cr:p1", "a.png", "b.png", 1),
        ("creativeranking", "val", "cr:p2", "c.png", "d.png", 0),
        ("creativeranking", "test", "cr:p3", "e.png", "f.png", 1),
    ]
    return pd.DataFrame(rows, columns=["dataset", "source_split", "group_id", "image_a", "image_b", "a_wins"])


def test_config_fractions_sum_to_one():
    cfg = load_config(CONFIG)
    assert sum(cfg["taste"]["fractions"].values()) == pytest.approx(1.0)


def test_groups_sharing_an_image_become_one_component():
    components = image_components(taste_pairs(5, shared=(1, 3)))
    assert components["taste:1"] == components["taste:3"]
    assert components.nunique() == 4


def test_hash_assignment_is_deterministic_and_follows_fractions():
    keys = [f"k{i}" for i in range(100)]
    first = assign_by_hash(keys, FRACTIONS, salt="s")
    assert first == assign_by_hash(list(reversed(keys)), FRACTIONS, salt="s")
    counts = pd.Series(first).value_counts().to_dict()
    assert counts == {"train": 70, "val": 15, "test": 15}
    with pytest.raises(ValueError):
        assign_by_hash(keys, {"train": 0.5, "val": 0.2, "test": 0.2}, salt="s")


def test_taste_split_has_no_shared_images_across_splits():
    pairs = split_taste(taste_pairs(40, shared=(2, 7)), {"fractions": FRACTIONS}, salt="v1")
    report = check_no_leakage(pairs)
    assert report["images_in_several_splits"] == 0
    assert set(pairs["split"]) == {"train", "val", "test"}
    linked = pairs[pairs["group_id"].isin(["taste:2", "taste:7"])]
    assert linked["split"].nunique() == 1


def test_creativeranking_keeps_its_original_split():
    pairs, info = split_creativeranking(cr_pairs())
    assert pairs["split"].tolist() == ["train", "val", "test"]
    assert check_no_leakage(pairs)["groups_in_several_splits"] == 0
    assert info["cross_split_images"] == 0


def test_creativeranking_image_reused_in_a_later_split_is_dropped_there():
    pairs = cr_pairs()
    pairs.loc[2, "image_a"] = "a.png"  # product p3 (test) reuses an image of p1 (train)
    pairs.loc[1, "image_b"] = "f.png"  # product p2 (val) reuses an image of p3 (test)
    kept, info = split_creativeranking(pairs)
    assert info["cross_split_images"] == 2
    assert info["dropped_cross_split_pairs"] == {"train": 0, "val": 0, "test": 1}
    assert kept["split"].tolist() == ["train", "val"]
    assert check_no_leakage(kept)["images_in_several_splits"] == 0


def test_leakage_is_detected():
    pairs, _ = split_creativeranking(cr_pairs())
    pairs.loc[2, "image_a"] = "a.png"  # the same image in train and test
    assert leakage_report(pairs)["images_in_several_splits"] == 1
    with pytest.raises(ValueError):
        check_no_leakage(pairs)
    pairs, _ = split_creativeranking(cr_pairs())
    pairs.loc[1, "split_group"] = "cr:p1"  # the same product in train and val
    with pytest.raises(ValueError):
        check_no_leakage(pairs)


def test_split_script_writes_outputs_under_data(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "ml_split_pairs.py"
    spec = importlib.util.spec_from_file_location("ml_split_pairs", script)
    split_script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(split_script)

    pairs_dir = tmp_path / "data/processed/pairs"
    pairs_dir.mkdir(parents=True)
    taste_pairs(20).to_parquet(pairs_dir / "taste.parquet")
    cr_pairs().to_parquet(pairs_dir / "creativeranking.parquet")

    stats = split_script.main(["--config", str(CONFIG)], repo_root=tmp_path)
    out = tmp_path / "data/processed/splits" / stats["config_version"]
    assert set(pd.read_parquet(out / "taste.parquet")["split"]) <= {"train", "val", "test"}
    assert json.loads((out / "stats.json").read_text())["taste"]["images_in_several_splits"] == 0
    with pytest.raises(SystemExit):
        split_script.main(["--config", str(CONFIG), "--out", "ml"], repo_root=tmp_path)
