"""Turn TASTE rankings and CreativeRanking logs into one preference-pair format.

Every output row compares two images of the same group (one design request
in TASTE, one product in CreativeRanking):

    dataset, source_split, group_id, image_a, image_b, a_wins, ...details

image_a < image_b (string order), so a_wins is 1 or 0 regardless of which
image won. Thresholds live in ml/data/pair_config.json, not in code.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

PAIR_COLUMNS = ["dataset", "source_split", "group_id", "image_a", "image_b", "a_wins"]
CREATIVERANKING_COLUMNS = ["item_id", "image", "ds", "pv", "clk"]


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _orient(df: pd.DataFrame, first: str, second: str, first_wins: pd.Series) -> pd.DataFrame:
    """Put the smaller image name in image_a and set a_wins accordingly."""
    swap = df[first] > df[second]
    out = df.copy()
    out["image_a"] = np.where(swap, df[second], df[first])
    out["image_b"] = np.where(swap, df[first], df[second])
    out["a_wins"] = np.where(swap, ~first_wins, first_wins).astype("int8")
    return out


def taste_pairs(rankings: pd.DataFrame, assets: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """One row per evaluator vote: 4 ranked images -> 6 pairs (rank 1 = best)."""
    rows = rankings[rankings["dimension"] == cfg["dimension"]]
    sizes = rows.groupby(["prompt_id", "evaluator_id"])["asset_id"].transform("size")
    ranks = rows.groupby(["prompt_id", "evaluator_id"])["rank"].transform("nunique")
    valid = rows[(sizes == cfg["group_size"]) & (ranks == cfg["group_size"])]
    dropped_groups = rows.groupby(["prompt_id", "evaluator_id"]).ngroups - valid.groupby(
        ["prompt_id", "evaluator_id"]
    ).ngroups

    paths = assets.set_index("asset_id")["image_path"]
    valid = valid.assign(image=valid["asset_id"].map(paths))
    keys = ["prompt_id", "evaluator_id"]
    merged = valid.merge(valid, on=keys, suffixes=("_1", "_2"))
    merged = merged[merged["image_1"] < merged["image_2"]]
    oriented = _orient(merged, "image_1", "image_2", merged["rank_1"] < merged["rank_2"])
    pairs = pd.DataFrame({
        "dataset": "taste",
        "source_split": None,  # TASTE has no official split; step 6 assigns one
        "group_id": "taste:" + oriented["prompt_id"].astype(str),
        "image_a": oriented["image_a"],
        "image_b": oriented["image_b"],
        "a_wins": oriented["a_wins"],
        "prompt_id": oriented["prompt_id"],
        "evaluator_id": oriented["evaluator_id"],
    }).reset_index(drop=True)
    stats = {
        "votes": int(valid.groupby(keys).ngroups),
        "dropped_vote_groups": int(dropped_groups),
        "pairs": len(pairs),
        "prompts": int(pairs["prompt_id"].nunique()),
        "images": int(pd.concat([pairs["image_a"], pairs["image_b"]]).nunique()),
    }
    return pairs, stats


def aggregate_images(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum the daily pv/clk of each (item_id, image)."""
    return rows.groupby(["item_id", "image"], as_index=False)[["pv", "clk"]].sum()


def two_proportion_z(clk_1, pv_1, clk_2, pv_2) -> np.ndarray:
    """z statistic of CTR_1 - CTR_2 with a pooled rate; 0 when undefined."""
    clk_1, pv_1, clk_2, pv_2 = (np.asarray(v, dtype=float) for v in (clk_1, pv_1, clk_2, pv_2))
    pooled = (clk_1 + clk_2) / (pv_1 + pv_2)
    se = np.sqrt(pooled * (1 - pooled) * (1 / pv_1 + 1 / pv_2))
    diff = clk_1 / pv_1 - clk_2 / pv_2
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(se > 0, diff / se, 0.0)
    return z


def _hash_order(values: pd.Series, salt: str) -> pd.Series:
    return values.map(lambda v: hashlib.sha256(f"{salt}:{v}".encode()).hexdigest())


def creativeranking_pairs(
    rows: pd.DataFrame, cfg: dict, split: str, salt: str
) -> tuple[pd.DataFrame, dict]:
    """Within-product pairs whose CTR difference is clear (|z| >= min_z)."""
    images = aggregate_images(rows)
    eligible = images[images["pv"] >= cfg["min_pv"]]
    merged = eligible.merge(eligible, on="item_id", suffixes=("_1", "_2"))
    merged = merged[merged["image_1"] < merged["image_2"]]
    candidate_pairs = len(merged)
    z = two_proportion_z(merged["clk_1"], merged["pv_1"], merged["clk_2"], merged["pv_2"])
    merged = merged.assign(z=z)
    clear = merged[np.abs(merged["z"]) >= cfg["min_z"]]

    # Deterministic product subset: hash order, first N products that have a pair.
    items = pd.Series(clear["item_id"].unique())
    chosen = items.iloc[np.argsort(_hash_order(items, salt).to_numpy())]
    chosen = set(chosen.iloc[: cfg["items_per_split"][split]])
    clear = clear[clear["item_id"].isin(chosen)]

    oriented = _orient(clear, "image_1", "image_2", clear["z"] > 0)
    swap = oriented["image_a"] != oriented["image_1"]
    pairs = pd.DataFrame({
        "dataset": "creativeranking",
        "source_split": split,
        "group_id": "cr:" + oriented["item_id"],
        "image_a": oriented["image_a"],
        "image_b": oriented["image_b"],
        "a_wins": oriented["a_wins"],
        "pv_a": np.where(swap, oriented["pv_2"], oriented["pv_1"]),
        "clk_a": np.where(swap, oriented["clk_2"], oriented["clk_1"]),
        "pv_b": np.where(swap, oriented["pv_1"], oriented["pv_2"]),
        "clk_b": np.where(swap, oriented["clk_1"], oriented["clk_2"]),
        "z": np.abs(oriented["z"]),
    }).reset_index(drop=True)
    stats = {
        "rows": len(rows),
        "images": len(images),
        "eligible_images": len(eligible),
        "candidate_pairs": int(candidate_pairs),
        "clear_pairs_all_items": int((np.abs(merged["z"]) >= cfg["min_z"]).sum()),
        "products_with_pairs": int(len(items)),
        "products_chosen": int(pairs["group_id"].nunique()),
        "pairs": len(pairs),
        "images_needed": int(pd.concat([pairs["image_a"], pairs["image_b"]]).nunique()),
    }
    return pairs, stats


def read_creativeranking_split(list_dir: Path, split: str) -> pd.DataFrame:
    return pd.read_csv(
        Path(list_dir) / f"{split}_data_list.txt",
        sep="\t",
        names=CREATIVERANKING_COLUMNS,
        dtype={"item_id": str, "image": str, "ds": "int16", "pv": "int64", "clk": "int64"},
    )
