"""Simple baselines to compare the preference model against.

Every baseline gives each image a score; a pair is predicted as "A wins"
when score_a > score_b. All baselines are scored on exactly the same pairs.

- random: a seeded coin flip per pair (about 0.5 by construction)
- rule: one image statistic (e.g. brightness) as the score, higher or lower
  is better; the statistic and direction are chosen on train pairs only
- laion_aesthetic: LAION-Aesthetics Predictor V1 for CLIP ViT-B/32, a linear
  layer on L2-normalized CLIP embeddings (MIT license, LAION-AI/aesthetic-predictor)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class FeatureCache:
    """One dataset of the step 7 cache: row order of index == row order of the arrays."""
    index: pd.DataFrame
    clip: np.ndarray
    stats: np.ndarray
    stat_names: list[str]

    @classmethod
    def load(cls, feature_dir: Path, dataset: str) -> "FeatureCache":
        manifest = json.loads((Path(feature_dir) / "manifest.json").read_text())
        index = pd.read_parquet(Path(feature_dir) / f"{dataset}_index.parquet")
        clip = np.load(Path(feature_dir) / f"{dataset}_clip.npy", allow_pickle=False)
        stats = np.load(Path(feature_dir) / f"{dataset}_stats.npy", allow_pickle=False)
        if not (len(index) == len(clip) == len(stats)) or not (index["row"] == np.arange(len(index))).all():
            raise ValueError(f"{dataset}: index and arrays do not line up")
        return cls(index, clip, stats, list(manifest["stats"]["columns"]))

    def rows(self, images: pd.Series) -> np.ndarray:
        lookup = pd.Series(self.index["row"].to_numpy(), index=self.index["image"])
        missing = ~images.isin(lookup.index)
        if missing.any():
            raise ValueError(f"{int(missing.sum())} pair images have no cached features")
        return lookup.loc[images].to_numpy()


def pairwise_accuracy(score_a: np.ndarray, score_b: np.ndarray, a_wins: np.ndarray) -> float:
    """Share of pairs where the higher score is the preferred image; ties count 0.5."""
    score_a, score_b = np.asarray(score_a, float), np.asarray(score_b, float)
    a_wins = np.asarray(a_wins).astype(bool)
    if len(a_wins) == 0:
        raise ValueError("no pairs to evaluate")
    correct = np.where(score_a == score_b, 0.5, (score_a > score_b) == a_wins)
    return float(np.mean(correct))


def standard_error(accuracy: float, n: int) -> float:
    return float(np.sqrt(accuracy * (1 - accuracy) / n))


def random_accuracy(a_wins: np.ndarray, seed: int) -> float:
    guess_a = np.random.default_rng(seed).random(len(a_wins)) < 0.5
    return float(np.mean(guess_a == np.asarray(a_wins).astype(bool)))


def rule_accuracies(stats_a: np.ndarray, stats_b: np.ndarray, a_wins: np.ndarray,
                    stat_names: list[str]) -> dict[str, float]:
    """Accuracy of every single-statistic rule, both directions ('+' higher wins, '-' lower wins)."""
    result = {}
    for col, name in enumerate(stat_names):
        result[f"{name}+"] = pairwise_accuracy(stats_a[:, col], stats_b[:, col], a_wins)
        result[f"{name}-"] = pairwise_accuracy(-stats_a[:, col], -stats_b[:, col], a_wins)
    return result


def load_laion_linear(path: Path, dim: int) -> tuple[np.ndarray, float]:
    """Weights of the LAION linear head (state dict with weight [1, dim] and bias [1])."""
    import torch

    state = torch.load(path, map_location="cpu", weights_only=True)  # no pickle code execution
    weight = state["weight"].detach().cpu().numpy().astype(np.float32)
    bias = state["bias"].detach().cpu().numpy().astype(np.float32)
    if weight.shape != (1, dim) or bias.shape != (1,):
        raise ValueError(f"expected weight (1, {dim}) and bias (1,), got {weight.shape} and {bias.shape}")
    return weight[0], float(bias[0])
