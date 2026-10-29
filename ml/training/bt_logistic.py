"""Logistic Bradley-Terry preference model on cached image features.

Each image gets a score s = w . z, where z is the image feature vector
(CLIP embedding + image statistics) standardized with the mean/std of the
TRAIN images only. For a pair, P(A preferred) = sigmoid(s_A - s_B), which is
the contract's bradley_terry_sigmoid_v1. Fitting is a logistic regression on
feature differences without intercept, with L2 regularization, solved by
full-batch L-BFGS in float64 on CPU, so the same data and config always give
the same weights.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch

SPLITS = ("train", "val", "test")


@dataclass
class ImageFeatures:
    """One dataset of the step 7 cache. Row order of index == row order of the arrays."""
    images: pd.Series
    matrix: np.ndarray  # [n_images, clip_dim + n_stats], float64
    columns: list[str]

    @classmethod
    def load(cls, feature_dir: Path, dataset: str) -> "ImageFeatures":
        feature_dir = Path(feature_dir)
        manifest = json.loads((feature_dir / "manifest.json").read_text())
        index = pd.read_parquet(feature_dir / f"{dataset}_index.parquet")
        clip = np.load(feature_dir / f"{dataset}_clip.npy", allow_pickle=False)
        stats = np.load(feature_dir / f"{dataset}_stats.npy", allow_pickle=False)
        if not (len(index) == len(clip) == len(stats)) or not (index["row"] == np.arange(len(index))).all():
            raise ValueError(f"{dataset}: index and arrays do not line up")
        columns = [f"clip_{i}" for i in range(clip.shape[1])] + list(manifest["stats"]["columns"])
        matrix = np.concatenate([clip, stats], axis=1).astype(np.float64)
        return cls(index["image"].reset_index(drop=True), matrix, columns)

    def rows(self, images: pd.Series) -> np.ndarray:
        lookup = pd.Series(np.arange(len(self.images)), index=self.images.to_numpy())
        missing = ~images.isin(lookup.index)
        if missing.any():
            raise ValueError(f"{int(missing.sum())} pair images have no cached features")
        return lookup.loc[images].to_numpy()


@dataclass
class PairSet:
    """Feature rows of both images, labels and per-pair weights for one split."""
    a: np.ndarray
    b: np.ndarray
    y: np.ndarray
    weight: np.ndarray
    dataset: np.ndarray


def pair_set(pairs: pd.DataFrame, features: ImageFeatures, split: str, dataset: str) -> PairSet:
    part = pairs[pairs["split"] == split]
    n = len(part)
    return PairSet(
        a=features.matrix[features.rows(part["image_a"])],
        b=features.matrix[features.rows(part["image_b"])],
        y=part["a_wins"].to_numpy().astype(np.float64),
        weight=np.full(n, 1.0 / max(n, 1)),  # every dataset counts equally in a joint fit
        dataset=np.full(n, dataset),
    )


def concat(sets: list[PairSet]) -> PairSet:
    joined = PairSet(*(np.concatenate([getattr(s, f) for s in sets]) for f in ("a", "b", "y", "weight", "dataset")))
    joined.weight = joined.weight / joined.weight.sum()
    return joined


@dataclass
class Scaler:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, train_images: np.ndarray) -> "Scaler":
        std = train_images.std(axis=0)
        return cls(train_images.mean(axis=0), np.where(std > 1e-12, std, 1.0))

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std


def fit_bt(train: PairSet, scaler: Scaler, l2: float, max_iter: int = 500) -> np.ndarray:
    """Weights w minimizing weighted logistic loss of (z_a - z_b) . w plus l2/2 * |w|^2."""
    diff = torch.from_numpy(scaler.transform(train.a) - scaler.transform(train.b))
    y = torch.from_numpy(train.y)
    weight = torch.from_numpy(train.weight)
    w = torch.zeros(diff.shape[1], dtype=torch.float64, requires_grad=True)
    optimizer = torch.optim.LBFGS([w], lr=1.0, max_iter=max_iter, tolerance_grad=1e-10,
                                  tolerance_change=1e-12, history_size=20, line_search_fn="strong_wolfe")

    def closure():
        optimizer.zero_grad()
        logits = diff @ w
        loss = (weight * torch.nn.functional.binary_cross_entropy_with_logits(
            logits, y, reduction="none")).sum() + 0.5 * l2 * (w @ w)
        loss.backward()
        return loss

    optimizer.step(closure)
    weights = w.detach().numpy().copy()
    if not np.isfinite(weights).all():
        raise ValueError("training produced non-finite weights")
    return weights


def scores(x: np.ndarray, scaler: Scaler, weights: np.ndarray) -> np.ndarray:
    return scaler.transform(x) @ weights


def pairwise_accuracy(score_a: np.ndarray, score_b: np.ndarray, a_wins: np.ndarray) -> float:
    """Share of pairs where the higher score is the preferred image; ties count 0.5."""
    a_wins = np.asarray(a_wins).astype(bool)
    if len(a_wins) == 0:
        raise ValueError("no pairs to evaluate")
    correct = np.where(score_a == score_b, 0.5, (score_a > score_b) == a_wins)
    return float(np.mean(correct))


def log_loss(score_a: np.ndarray, score_b: np.ndarray, a_wins: np.ndarray) -> float:
    logits = torch.from_numpy(np.asarray(score_a - score_b, dtype=np.float64))
    target = torch.from_numpy(np.asarray(a_wins, dtype=np.float64))
    return float(torch.nn.functional.binary_cross_entropy_with_logits(logits, target))
