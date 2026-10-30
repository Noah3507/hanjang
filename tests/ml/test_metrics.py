"""Hand-checkable examples for the step 10 metrics."""

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.metrics import (
    accuracy_by_confidence,
    cluster_bootstrap,
    correct,
    creativeranking_product_groups,
    designer_agreement,
    ranking_metrics,
    taste_vote_groups,
)


def test_correct_counts_ties_as_half():
    assert correct([2, 1, 3], [1, 2, 3], [1, 1, 0]).tolist() == [1.0, 0.0, 0.5]


def test_bootstrap_mean_is_exact_and_interval_contains_it():
    values = np.array([1, 1, 0, 1, 0, 0, 1, 1.0])
    groups = np.array(["a", "a", "b", "b", "c", "c", "d", "d"])
    result = cluster_bootstrap(values, groups, reps=500, seed=0)
    assert result["mean"] == pytest.approx(5 / 8)
    assert result["ci95"][0] <= 5 / 8 <= result["ci95"][1]
    assert result["groups"] == 4 and result["pairs"] == 8
    assert cluster_bootstrap(values, groups, reps=500, seed=0) == result  # seeded


def test_bootstrap_of_identical_groups_has_no_width():
    result = cluster_bootstrap(np.ones(6), np.array(list("aabbcc")), reps=200)
    assert result["ci95"] == [1.0, 1.0]


def test_top1_and_tau_by_hand():
    perfect = (np.array([4.0, 3, 2, 1]), np.array([3.0, 2, 1, 0]))  # same order: top1 1, tau 1
    reversed_ = (np.array([1.0, 2, 3, 4]), np.array([3.0, 2, 1, 0]))  # opposite: top1 0, tau -1
    result = ranking_metrics({"g1": perfect, "g2": reversed_})
    assert result["top1"] == 0.5 and result["kendall_tau"] == 0.0
    assert result["top1_random"] == 0.25 and result["groups"] == 2


def test_taste_vote_groups_rebuild_the_ranking():
    # one vote ranking a > b > c > d, written as the 6 ordered pairs of the split files
    order = ["a.png", "b.png", "c.png", "d.png"]
    rows = [(order[i], order[j], 1, 7, "e1") for i in range(4) for j in range(i + 1, 4)]
    pairs = pd.DataFrame(rows, columns=["image_a", "image_b", "a_wins", "prompt_id", "evaluator_id"])
    groups = taste_vote_groups(pairs, {"a.png": 4, "b.png": 3, "c.png": 2, "d.png": 1})
    scores, wins = next(iter(groups.values()))
    assert wins.tolist() == [3, 2, 1, 0] and scores.tolist() == [4, 3, 2, 1]


def test_creativeranking_groups_use_observed_ctr():
    pairs = pd.DataFrame({"group_id": ["cr:p1", "cr:p1"], "image_a": ["x", "x"], "image_b": ["y", "z"],
                          "pv_a": [1000, 1000], "clk_a": [80, 80], "pv_b": [1000, 500], "clk_b": [20, 30]})
    scores, ctr = creativeranking_product_groups(pairs, {"x": 1.0, "y": 0.0, "z": 0.5})["cr:p1"]
    assert ctr.tolist() == pytest.approx([0.08, 0.02, 0.06]) and scores.tolist() == [1.0, 0.0, 0.5]


def test_designer_agreement_against_the_pair_majority():
    pairs = pd.DataFrame({"image_a": ["a"] * 4 + ["c"] * 2, "image_b": ["b"] * 4 + ["d"] * 2,
                          "a_wins": [1, 1, 1, 0, 1, 0]})
    # pair a-b: 3 of 4 votes agree with the majority; pair c-d is an even split (0.5 each)
    assert designer_agreement(pairs) == pytest.approx((3 + 0.5 * 2) / 6)


def test_accuracy_by_confidence_bins():
    diff = np.array([0.0, 0.1, 3.0, -3.0])
    bins = accuracy_by_confidence(diff, np.array([0.5, 1.0, 1.0, 0.0]))
    assert bins[0]["pairs"] == 2 and bins[0]["accuracy"] == pytest.approx(0.75)
    assert bins[-1]["pairs"] == 2 and bins[-1]["accuracy"] == pytest.approx(0.5)
