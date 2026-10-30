"""Final-evaluation metrics (step 10). Pure numpy/pandas, no model code.

Every metric takes model scores per pair or per image, so the same functions
score the CreativeRanking model, the TASTE model and the baselines.
- pairwise accuracy: share of pairs where the higher score is the preferred image (ties 0.5)
- cluster bootstrap: 95% interval that resamples whole groups (TASTE image components,
  CreativeRanking products), because pairs inside a group are not independent
- Top-1 and Kendall's tau per ranking group (one TASTE vote of 4 images, one product)
- designer agreement: how often a vote agrees with the majority of its image pair
  (a reference for rater consistency, not an independent human ceiling)
- accuracy by score gap |s_A - s_B|: the gap is not a calibrated probability
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def correct(score_a: np.ndarray, score_b: np.ndarray, a_wins: np.ndarray) -> np.ndarray:
    """Per-pair credit: 1 right, 0 wrong, 0.5 when the two scores are equal."""
    score_a, score_b = np.asarray(score_a, float), np.asarray(score_b, float)
    a_wins = np.asarray(a_wins).astype(bool)
    return np.where(score_a == score_b, 0.5, ((score_a > score_b) == a_wins).astype(float))


def cluster_bootstrap(values: np.ndarray, groups: np.ndarray, reps: int = 2000, seed: int = 0) -> dict:
    """Mean of per-pair values with a 95% percentile interval over resampled groups."""
    values, groups = np.asarray(values, float), np.asarray(groups)
    if len(values) == 0:
        raise ValueError("no pairs to evaluate")
    codes, uniques = pd.factorize(groups)
    sums = np.bincount(codes, weights=values, minlength=len(uniques))
    counts = np.bincount(codes, minlength=len(uniques)).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(uniques), size=(reps, len(uniques)))
    stats = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    low, high = np.percentile(stats, [2.5, 97.5])
    return {"mean": float(values.mean()), "ci95": [float(low), float(high)],
            "pairs": int(len(values)), "groups": int(len(uniques))}


def _tau(scores: np.ndarray, truth: np.ndarray) -> float | None:
    """Kendall's tau-a over the pairs that the truth orders; model ties count 0."""
    total, concord = 0, 0.0
    for i in range(len(scores)):
        for j in range(i + 1, len(scores)):
            if truth[i] == truth[j]:
                continue
            total += 1
            concord += np.sign(scores[i] - scores[j]) * np.sign(truth[i] - truth[j])
    return None if total == 0 else concord / total


def _top1(scores: np.ndarray, truth: np.ndarray) -> float:
    """1 if the model's best image has the best truth value; shared model maxima split the credit."""
    best_model = np.flatnonzero(scores == scores.max())
    return float(np.mean(truth[best_model] == truth.max()))


def ranking_metrics(groups: dict[str, tuple[np.ndarray, np.ndarray]]) -> dict:
    """Top-1, Kendall's tau and the random Top-1 reference over ranking groups.

    groups maps a group id to (model scores, truth values; higher truth = preferred).
    """
    top1, taus, chance = [], [], []
    for scores, truth in groups.values():
        scores, truth = np.asarray(scores, float), np.asarray(truth, float)
        if len(scores) < 2:
            continue
        top1.append(_top1(scores, truth))
        chance.append(float(np.mean(truth == truth.max())))
        tau = _tau(scores, truth)
        if tau is not None:
            taus.append(tau)
    return {"groups": len(top1), "top1": float(np.mean(top1)), "top1_random": float(np.mean(chance)),
            "kendall_tau": float(np.mean(taus))}


def taste_vote_groups(pairs: pd.DataFrame, image_score: dict) -> dict:
    """One group per vote (prompt_id, evaluator_id): truth = wins inside the vote (rank 1 wins 3)."""
    groups = {}
    for key, part in pairs.groupby(["prompt_id", "evaluator_id"]):
        wins = pd.concat([part.loc[part["a_wins"] == 1, "image_a"], part.loc[part["a_wins"] == 0, "image_b"]])
        images = sorted(set(part["image_a"]) | set(part["image_b"]))
        counts = wins.value_counts()
        groups[str(key)] = (np.array([image_score[i] for i in images]),
                            np.array([counts.get(i, 0) for i in images], float))
    return groups


def creativeranking_product_groups(pairs: pd.DataFrame, image_score: dict) -> dict:
    """One group per product: truth = observed CTR (clicks / impressions) of each image."""
    rows = pd.concat([
        pairs[["group_id", "image_a", "pv_a", "clk_a"]].set_axis(["group_id", "image", "pv", "clk"], axis=1),
        pairs[["group_id", "image_b", "pv_b", "clk_b"]].set_axis(["group_id", "image", "pv", "clk"], axis=1),
    ]).drop_duplicates(["group_id", "image"])
    groups = {}
    for product, part in rows.groupby("group_id"):
        groups[str(product)] = (np.array([image_score[i] for i in part["image"]]),
                                (part["clk"] / part["pv"]).to_numpy(float))
    return groups


def same_partition(first: np.ndarray, second: np.ndarray) -> bool:
    """True when two labelings group the same items together (label names may differ)."""
    table = pd.DataFrame({"a": np.asarray(first), "b": np.asarray(second)}).drop_duplicates()
    return bool(table["a"].is_unique and table["b"].is_unique)


def designer_agreement(pairs: pd.DataFrame) -> float:
    """Share of votes that agree with the majority vote of the same image pair (even split = 0.5).

    The majority includes the vote itself, so this is a reference for rater consistency,
    not an independent upper bound on what a model can reach."""
    share = pairs.groupby(["image_a", "image_b"])["a_wins"].transform("mean")
    agree = np.where(share == 0.5, 0.5, np.where(share > 0.5, pairs["a_wins"] == 1, pairs["a_wins"] == 0))
    return float(np.mean(agree))


def accuracy_by_score_gap(diff: np.ndarray, credit: np.ndarray,
                          edges: tuple = (0.0, 0.2, 0.4, 0.8, 1.4, np.inf)) -> list[dict]:
    """Accuracy of pairs grouped by the model score gap |s_A - s_B|.

    sigmoid(gap) is the model's output, but its calibration is not verified, so the
    bins are reported as score gaps, not as predicted probabilities."""
    gap = np.abs(np.asarray(diff, float))
    out = []
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (gap >= low) & (gap < high)
        out.append({"gap_from": low, "gap_to": None if np.isinf(high) else high, "pairs": int(mask.sum()),
                    "accuracy": float(credit[mask].mean()) if mask.any() else None})
    return out
