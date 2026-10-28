"""Assign train/val/test to preference pairs without leakage.

- TASTE has no official split. Design requests that share any image are
  merged into one split group (connected components), then whole groups
  are assigned by a hash order, so an image never appears in two splits.
- CreativeRanking keeps its original split (products never overlap).

The same config always gives the same split. leakage_report() is the
reproducible check A asked for; check_no_leakage() fails loudly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

SPLITS = ("train", "val", "test")


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _hash(value: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def image_components(pairs: pd.DataFrame, group_col: str = "group_id") -> pd.Series:
    """Map each group to a component id; groups sharing an image share a component."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        while parent.setdefault(node, node) != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)

    for group, image_a, image_b in pairs[[group_col, "image_a", "image_b"]].itertuples(index=False):
        union("g:" + str(group), "i:" + image_a)
        union("g:" + str(group), "i:" + image_b)

    groups = pairs[group_col].drop_duplicates()
    return pd.Series([find("g:" + str(g)) for g in groups], index=groups.to_numpy(), name="component")


def assign_by_hash(keys: list[str], fractions: dict, salt: str) -> dict[str, str]:
    """Deterministically give each key a split with the configured fractions."""
    if abs(sum(fractions[s] for s in SPLITS) - 1.0) > 1e-9:
        raise ValueError(f"fractions must sum to 1, got {fractions}")
    ordered = sorted(keys, key=lambda k: _hash(k, salt))
    n_train = round(len(ordered) * fractions["train"])
    n_val = round(len(ordered) * fractions["val"])
    result = {}
    for i, key in enumerate(ordered):
        result[key] = "train" if i < n_train else "val" if i < n_train + n_val else "test"
    return result


def split_taste(pairs: pd.DataFrame, cfg: dict, salt: str) -> pd.DataFrame:
    components = image_components(pairs)
    assignment = assign_by_hash(sorted(set(components)), cfg["fractions"], salt)
    split_group = pairs["group_id"].map(components)
    return pairs.assign(split_group=split_group, split=split_group.map(assignment))


def split_creativeranking(pairs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep the original split; drop pairs whose image already lives in an earlier split.

    First the original data is checked: a product (group_id) must belong to
    exactly one source_split, otherwise this fails before anything is removed.
    Products never overlap across the original splits, but the same image
    file can be reused by products in different splits. Such an image is kept
    only in its earliest split (train, then val, then test), and pairs using
    it in a later split are removed. Removed pairs and products that lost all
    their pairs are counted per split.
    """
    if not pairs["source_split"].isin(SPLITS).all():
        raise ValueError("CreativeRanking pairs need source_split train/val/test")
    splits_per_group = pairs.groupby("group_id")["source_split"].nunique()
    crossing = splits_per_group[splits_per_group > 1]
    if len(crossing):
        raise ValueError(
            f"{len(crossing)} CreativeRanking groups appear in several source splits, "
            f"e.g. {list(crossing.index[:3])}"
        )
    out = pairs.assign(split_group=pairs["group_id"], split=pairs["source_split"])
    order = out["split"].map({s: i for i, s in enumerate(SPLITS)})
    images = pd.concat([
        pd.DataFrame({"image": out["image_a"], "order": order}),
        pd.DataFrame({"image": out["image_b"], "order": order}),
    ])
    first = images.groupby("image")["order"].min()
    keep = (out["image_a"].map(first) == order) & (out["image_b"].map(first) == order)
    kept = out[keep].reset_index(drop=True)
    groups_before = out.groupby("split")["split_group"].nunique()
    groups_after = kept.groupby("split")["split_group"].nunique()
    info = {
        "cross_split_images": int((images.groupby("image")["order"].nunique() > 1).sum()),
        "dropped_cross_split_pairs": {s: int((~keep & (out["split"] == s)).sum()) for s in SPLITS},
        "groups_emptied_by_dedup": {
            s: int(groups_before.get(s, 0) - groups_after.get(s, 0)) for s in SPLITS
        },
    }
    return kept, info


def leakage_report(pairs: pd.DataFrame) -> dict:
    """Count groups and images that appear in more than one split."""
    groups = pairs.groupby("split_group")["split"].nunique()
    images = pd.concat([
        pairs[["image_a", "split"]].rename(columns={"image_a": "image"}),
        pairs[["image_b", "split"]].rename(columns={"image_b": "image"}),
    ]).groupby("image")["split"].nunique()
    return {
        "groups_in_several_splits": int((groups > 1).sum()),
        "images_in_several_splits": int((images > 1).sum()),
        "pairs_per_split": {s: int((pairs["split"] == s).sum()) for s in SPLITS},
        "groups_per_split": {
            s: int(pairs.loc[pairs["split"] == s, "split_group"].nunique()) for s in SPLITS
        },
    }


def check_no_leakage(pairs: pd.DataFrame) -> dict:
    report = leakage_report(pairs)
    if report["groups_in_several_splits"] or report["images_in_several_splits"]:
        raise ValueError(f"split leakage found: {report}")
    return report
