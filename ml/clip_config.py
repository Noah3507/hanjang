"""CLIP encoder settings for the preference model.

The encoder is NOT fixed yet (RANKING_CONTRACT_V1_1: encoder, pretrained
tag, input size and feature dimension come from metadata). Candidates are
compared on CPU memory and latency before one is chosen with A.
Nothing here downloads weights.
"""

from __future__ import annotations

import open_clip

# Candidates to measure. Order does not mean preference.
CLIP_CANDIDATES: tuple[str, ...] = ("ViT-B-32", "ViT-B-16", "ViT-L-14")
PRETRAINED_TAG = "openai"


def embedding_dim(model_name: str) -> int:
    """Return the embedding size from open_clip's model config (no download)."""
    config = open_clip.get_model_config(model_name)
    if config is None:
        raise ValueError(f"Unknown open_clip model: {model_name}")
    return int(config["embed_dim"])


def input_size(model_name: str) -> int:
    """Return the square image input size from the model config (no download)."""
    config = open_clip.get_model_config(model_name)
    if config is None:
        raise ValueError(f"Unknown open_clip model: {model_name}")
    size = config["vision_cfg"]["image_size"]
    return int(size[0] if isinstance(size, (list, tuple)) else size)