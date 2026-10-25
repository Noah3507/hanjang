"""Lightweight smoke tests for the ML environment.

These tests download no model weights and need no dataset.
Run from the repository root: python -m pytest tests/ml
"""

import pytest
import torch

from ml.clip_config import CLIP_CANDIDATES, PRETRAINED_TAG, embedding_dim, input_size
from ml.device import select_device


def test_core_libraries_import():
    import open_clip

    assert torch.__version__
    assert open_clip.__version__


def test_select_device_returns_usable_device():
    device = select_device()
    assert device.type in {"cuda", "mps", "cpu"}
    x = torch.ones(2, 3, device=device)
    assert x.sum().item() == 6


def test_select_device_respects_preferred():
    assert select_device("cpu").type == "cpu"


@pytest.mark.parametrize("model_name", CLIP_CANDIDATES)
def test_clip_candidate_metadata_without_download(model_name):
    import open_clip

    assert model_name in open_clip.list_models()
    assert PRETRAINED_TAG in open_clip.list_pretrained_tags_by_model(model_name)
    assert embedding_dim(model_name) > 0
    assert input_size(model_name) > 0


def test_unknown_clip_model_is_rejected():
    with pytest.raises(ValueError):
        embedding_dim("not-a-real-model")


def test_pairwise_preference_probability_shape():
    # Bradley-Terry: P(A preferred over B) = sigmoid(s_A - s_B)
    scores = torch.tensor([1.84, 1.10, 0.32, -0.40])
    prob = torch.sigmoid(scores[:, None] - scores[None, :])
    assert prob.shape == (4, 4)
    assert torch.allclose(prob.diagonal(), torch.full((4,), 0.5))
    assert torch.allclose(prob + prob.T, torch.ones(4, 4))