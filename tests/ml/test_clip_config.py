"""QuickGELU must match the pretrained weights. No weights are downloaded."""

import pytest

from ml.clip_config import CLIP_CANDIDATES, PRETRAINED_TAG, uses_quick_gelu


@pytest.mark.parametrize("model_name", CLIP_CANDIDATES)
def test_openai_weights_use_quick_gelu(model_name):
    assert uses_quick_gelu(model_name, PRETRAINED_TAG) is True


def test_unknown_tag_does_not_force_quick_gelu():
    assert uses_quick_gelu("ViT-B-32", "no-such-tag") is False
