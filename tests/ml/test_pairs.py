"""Tests for preference-pair building. Uses tiny synthetic data only."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.data.pairs import (
    PAIR_COLUMNS,
    creativeranking_pairs,
    load_config,
    taste_pairs,
    two_proportion_z,
)

CONFIG = Path(__file__).resolve().parents[2] / "ml" / "data" / "pair_config.json"
TASTE_CFG = {"dimension": "preference", "group_size": 4}
CR_CFG = {"min_pv": 100, "min_z": 1.96, "items_per_split": {"train": 10}}


def taste_tables():
    assets = pd.DataFrame({"asset_id": [1, 2, 3, 4], "image_path": [f"images/{i}.png" for i in "abcd"]})
    rows = []
    # evaluator e1 ranks a > b > c > d; evaluator e2 ranks d > c > b > a
    for evaluator, order in [("e1", [1, 2, 3, 4]), ("e2", [4, 3, 2, 1])]:
        for asset, rank in zip([1, 2, 3, 4], order):
            rows.append(("preference", 10, asset, evaluator, rank))
    # a duplicated 8-row vote group and another dimension, both ignored
    for asset, rank in zip([1, 2, 3, 4] * 2, [1, 2, 3, 4] * 2):
        rows.append(("preference", 11, asset, "e3", rank))
    for asset, rank in zip([1, 2, 3, 4], [1, 2, 3, 4]):
        rows.append(("typography", 12, asset, "e1", rank))
    rankings = pd.DataFrame(rows, columns=["dimension", "prompt_id", "asset_id", "evaluator_id", "rank"])
    return rankings, assets


def cr_rows(images):
    """images: list of (item_id, image, pv, clk), spread over two days."""
    rows = []
    for item, image, pv, clk in images:
        rows.append((item, image, 0, pv // 2, clk // 2))
        rows.append((item, image, 1, pv - pv // 2, clk - clk // 2))
    return pd.DataFrame(rows, columns=["item_id", "image", "ds", "pv", "clk"])


def test_config_file_has_required_keys():
    cfg = load_config(CONFIG)
    assert cfg["taste"]["dimension"] == "preference"
    assert set(cfg["creativeranking"]["items_per_split"]) == {"train", "val", "test"}


def test_taste_one_vote_gives_six_pairs_with_rank_one_best():
    rankings, assets = taste_tables()
    pairs, stats = taste_pairs(rankings, assets, TASTE_CFG)
    assert list(pairs.columns[:6]) == PAIR_COLUMNS
    assert stats["votes"] == 2 and stats["dropped_vote_groups"] == 1
    assert len(pairs) == 12
    e1 = pairs[pairs["evaluator_id"] == "e1"]
    # image a has rank 1 for e1, so it wins every pair it is in
    assert e1[e1["image_a"] == "images/a.png"]["a_wins"].tolist() == [1, 1, 1]
    e2 = pairs[pairs["evaluator_id"] == "e2"]
    assert e2[e2["image_a"] == "images/a.png"]["a_wins"].tolist() == [0, 0, 0]


def test_pairs_are_ordered_and_never_self_pairs():
    rankings, assets = taste_tables()
    pairs, _ = taste_pairs(rankings, assets, TASTE_CFG)
    assert (pairs["image_a"] < pairs["image_b"]).all()


def test_z_statistic_sign_and_undefined_case():
    z = two_proportion_z([50, 0], [1000, 500], [10, 0], [1000, 500])
    assert z[0] > 1.96
    assert z[1] == 0.0  # no clicks on either side: no evidence


def test_creativeranking_keeps_only_clear_within_product_pairs():
    rows = cr_rows([
        ("p1", "x.png", 1000, 80),   # 8% CTR
        ("p1", "y.png", 1000, 20),   # 2% CTR -> clear loser
        ("p1", "z.png", 1000, 21),   # vs y: not clear
        ("p1", "low.png", 50, 10),   # pv below min_pv: dropped
        ("p2", "q.png", 1000, 80),   # other product: never paired with p1
    ])
    pairs, stats = creativeranking_pairs(rows, CR_CFG, "train", salt="t")
    assert stats["images"] == 5 and stats["eligible_images"] == 4
    assert set(zip(pairs["image_a"], pairs["image_b"])) == {("x.png", "y.png"), ("x.png", "z.png")}
    assert pairs["a_wins"].tolist() == [1, 1]
    assert (pairs["pv_a"] == 1000).all() and (pairs["clk_a"] == 80).all()
    assert set(pairs["group_id"]) == {"cr:p1"}


def test_winner_is_the_higher_ctr_even_when_its_name_sorts_last():
    rows = cr_rows([("p1", "a.png", 1000, 10), ("p1", "b.png", 1000, 60)])
    pairs, _ = creativeranking_pairs(rows, CR_CFG, "train", salt="t")
    assert pairs[["image_a", "image_b", "a_wins"]].values.tolist() == [["a.png", "b.png", 0]]
    assert pairs.loc[0, "clk_b"] == 60


def test_product_subset_is_deterministic_and_capped():
    images = []
    for i in range(30):
        images += [(f"p{i}", f"{i}a.png", 1000, 80), (f"p{i}", f"{i}b.png", 1000, 10)]
    rows = cr_rows(images)
    first, stats = creativeranking_pairs(rows, CR_CFG, "train", salt="v1")
    again, _ = creativeranking_pairs(rows, CR_CFG, "train", salt="v1")
    assert stats["products_with_pairs"] == 30 and stats["products_chosen"] == 10
    assert first.equals(again)


def test_build_script_writes_outputs_under_data(tmp_path):
    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts" / "ml_build_pairs.py"
    spec = importlib.util.spec_from_file_location("ml_build_pairs", script)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    taste = tmp_path / "data/raw/taste"
    taste.mkdir(parents=True)
    rankings, assets = taste_tables()
    rankings.to_parquet(taste / "rankings.parquet")
    assets.to_parquet(taste / "assets.parquet")
    cr = tmp_path / "data/raw/creativeranking/list/list"
    cr.mkdir(parents=True)
    for split in ("train", "val", "test"):
        cr_rows([("p1", "x.png", 1000, 80), ("p1", "y.png", 1000, 20)]).to_csv(
            cr / f"{split}_data_list.txt", sep="\t", header=False, index=False
        )

    stats = build.main(["--config", str(CONFIG)], repo_root=tmp_path)
    out = tmp_path / "data/processed/pairs"
    assert len(pd.read_parquet(out / "taste.parquet")) == 12
    assert len(pd.read_parquet(out / "creativeranking.parquet")) == 3
    assert json.loads((out / "stats.json").read_text())["config_version"] == stats["config_version"]
    with pytest.raises(SystemExit):
        build.main(["--config", str(CONFIG), "--out", "ml"], repo_root=tmp_path)


def test_taste_drops_invalid_vote_groups_by_reason():
    rankings, assets = taste_tables()
    # asset 5 shares asset 4's image path; asset 99 has no image row
    assets = pd.concat([assets, pd.DataFrame({"asset_id": [5], "image_path": ["images/d.png"]})])
    bad = [
        (20, [1, 1, 2, 3], [1, 2, 3, 4]),   # the same asset twice
        (21, [1, 2, 3, 4], [2, 3, 4, 5]),   # ranks not exactly 1..4
        (22, [1, 2, 3, 99], [1, 2, 3, 4]),  # asset without an image path
        (23, [1, 2, 4, 5], [1, 2, 3, 4]),   # two assets, one image path
    ]
    rows = [("preference", prompt, asset, "e9", rank)
            for prompt, ids, ranks in bad for asset, rank in zip(ids, ranks)]
    rankings = pd.concat([rankings, pd.DataFrame(rows, columns=rankings.columns)], ignore_index=True)
    pairs, stats = taste_pairs(rankings, assets, TASTE_CFG)
    assert stats["votes"] == 2 and len(pairs) == 12
    assert stats["dropped_by_reason"] == {
        "duplicate_asset": 1,
        "duplicate_image_path": 1,
        "missing_image_path": 1,
        "ranks_not_1_to_n": 1,
        "wrong_row_count": 1,
    }
    assert set(pairs["prompt_id"]) == {10}


def test_duplicated_asset_ids_in_assets_are_an_error():
    rankings, assets = taste_tables()
    with pytest.raises(ValueError):
        taste_pairs(rankings, pd.concat([assets, assets.iloc[[0]]]), TASTE_CFG)


@pytest.mark.parametrize(
    "column, value",
    [("pv", -1), ("clk", -1), ("clk", 10_000), ("pv", None), ("image", None)],
)
def test_invalid_creativeranking_rows_are_errors(column, value):
    rows = cr_rows([("p1", "x.png", 1000, 80), ("p1", "y.png", 1000, 20)]).astype({"pv": "object", "clk": "object"})
    rows.loc[0, column] = value
    with pytest.raises(ValueError):
        creativeranking_pairs(rows, CR_CFG, "train", salt="t")


def _load_build_script():
    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts" / "ml_build_pairs.py"
    spec = importlib.util.spec_from_file_location("ml_build_pairs", script)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build


def _write_raw(tmp_path, bad_test_split=False):
    taste = tmp_path / "data/raw/taste"
    taste.mkdir(parents=True, exist_ok=True)
    rankings, assets = taste_tables()
    rankings.to_parquet(taste / "rankings.parquet")
    assets.to_parquet(taste / "assets.parquet")
    cr = tmp_path / "data/raw/creativeranking/list/list"
    cr.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        clicks = 2000 if (bad_test_split and split == "test") else 80  # clk > pv
        cr_rows([("p1", "x.png", 1000, clicks), ("p1", "y.png", 1000, 20)]).to_csv(
            cr / f"{split}_data_list.txt", sep="\t", header=False, index=False
        )


def test_failed_run_leaves_previous_results_untouched(tmp_path):
    build = _load_build_script()
    _write_raw(tmp_path)
    build.main(["--config", str(CONFIG)], repo_root=tmp_path)
    out = tmp_path / "data/processed/pairs"
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    _write_raw(tmp_path, bad_test_split=True)  # the last step now fails
    with pytest.raises(ValueError):
        build.main(["--config", str(CONFIG)], repo_root=tmp_path)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert [p.name for p in out.parent.iterdir()] == ["pairs"]  # no temporary folders left


def test_stats_record_code_and_input_checksums(tmp_path):
    build = _load_build_script()
    _write_raw(tmp_path)
    (tmp_path / "data/raw/taste/provenance.json").write_text(json.dumps({"repo_id": "x/taste"}))
    stats = build.main(["--config", str(CONFIG)], repo_root=tmp_path)
    assert set(stats["code"]) == {"commit", "dirty"}
    assert set(stats["inputs"]) == {
        "taste_rankings", "taste_assets",
        "creativeranking_train", "creativeranking_val", "creativeranking_test",
    }
    assert all(len(v["sha256"]) == 64 for v in stats["inputs"].values())
    assert stats["sources"]["taste"] == {"repo_id": "x/taste"}
