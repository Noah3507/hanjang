"""Inference package for the service ranking (owned by B, contract agreed with A on 2026-10-31).

    from ml.inference import load_model, extract_features, score_ad, rank_ads, RankInput

Runs in .venv-rank (ml/inference/requirements.txt): no pandas, no network.
"""

from ml.inference.api import (
    FeatureVector,
    ModelHandle,
    RankInput,
    extract_features,
    load_model,
    rank_ads,
    score_ad,
)
from ml.inference.errors import (
    ArtifactMismatch,
    InferenceFailure,
    InvalidImage,
    ModelNotAvailable,
    RankingError,
)

__all__ = [
    "ArtifactMismatch", "FeatureVector", "InferenceFailure", "InvalidImage", "ModelHandle",
    "ModelNotAvailable", "RankInput", "RankingError", "extract_features", "load_model", "rank_ads", "score_ad",
]
