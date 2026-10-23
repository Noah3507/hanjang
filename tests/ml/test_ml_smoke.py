"""Lightweight smoke tests for the ML environment.

These tests download no model weights and need no dataset.
Run from the repository root: python -m pytest tests/ml
"""

import torch

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


def test_clip_vit_l14_embedding_size_without_download():
    import open_clip

    config = open_clip.get_model_config("ViT-L-14")
    assert config is not None
    assert config["embed_dim"] == 768


def test_pairwise_preference_probability_shape():
    # Bradley-Terry: P(A preferred over B) = sigmoid(s_A - s_B)
    scores = torch.tensor([1.84, 1.10, 0.32, -0.40])
    prob = torch.sigmoid(scores[:, None] - scores[None, :])
    assert prob.shape == (4, 4)
    assert torch.allclose(prob.diagonal(), torch.full((4,), 0.5))
    assert torch.allclose(prob + prob.T, torch.ones(4, 4))