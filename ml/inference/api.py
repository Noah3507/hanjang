"""The four functions the service calls (docs/RANKING_CONTRACT_V1_1.md, agreed with A on 2026-10-31).

    load_model(artifact_dir)              -> ModelHandle   (once per worker)
    extract_features(image_path, model)   -> FeatureVector (float64, read-only, model.feature_columns order)
    score_ad(image_path, model)           -> float         (raw score, higher = preferred)
    rank_ads(items, model)                -> dict          (rank-output.schema.json, items in input order)

Features are computed exactly as in training (ml/features): the ad is padded
to a white square (pad-square-v1), encoded by CLIP ViT-B/32 with QuickGELU
and L2-normalized, and the four image statistics come from the original ad.
Each image is encoded on its own, so rank_ads and score_ad give the same score
for the same file. Everything runs on CPU without gradients and without network.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

import numpy as np
import open_clip
import torch
from PIL import Image, UnidentifiedImageError
from safetensors.numpy import load_file as load_numpy
from safetensors.torch import load_file as load_torch

from ml.features.clip_features import ClipEncoder, feature_version
from ml.features.image_stats import STATS_VERSION, image_stats
from ml.features.preprocess import DEFAULT_PAD_COLOR, PREPROCESSING_VERSION
from ml.inference.bundle import METHOD, read_manifest, safe_member, verify_files, verify_packages
from ml.inference.errors import ArtifactMismatch, InferenceFailure, InvalidImage, ModelNotAvailable

FeatureVector = np.ndarray  # float64, shape (len(model.feature_columns),), finite, read-only
AD_SIZE = (1080, 1350)


@dataclass(frozen=True)
class RankInput:
    candidate_id: str
    rendered_image_path: Path


@dataclass(frozen=True)
class ModelHandle:
    """A loaded bundle. Fields cannot be reassigned and the arrays are read-only."""
    model_version: str
    feature_version: str
    preprocessing_version: str
    method: str
    clip: MappingProxyType
    feature_columns: tuple[str, ...]
    close_call_score_gap: float
    device: str = "cpu"
    _scaler_mean: np.ndarray = field(repr=False, default=None)
    _scaler_std: np.ndarray = field(repr=False, default=None)
    _weights: np.ndarray = field(repr=False, default=None)
    _encoder: ClipEncoder = field(repr=False, default=None)


def _read_only(array: np.ndarray) -> np.ndarray:
    array = np.array(array, dtype=np.float64, copy=True)
    array.setflags(write=False)
    return array


def _load_encoder(root: Path, clip: dict) -> ClipEncoder:
    """Build the CLIP architecture without any download, then load the image tower from the bundle."""
    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            clip["model"], pretrained=None, force_quick_gelu=bool(clip["quick_gelu"]))
        state = load_torch(str(safe_member(root, clip["weights_file"])))
        model.visual.load_state_dict(state, strict=True)
    except ArtifactMismatch:
        raise
    except (KeyError, RuntimeError, ValueError) as error:
        raise ArtifactMismatch("CLIP weights do not fit the CLIP settings in the manifest") from error
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    size = model.visual.image_size
    size = size[0] if isinstance(size, (tuple, list)) else size
    if int(model.visual.output_dim) != int(clip["embedding_dim"]) or int(size) != int(clip["input_size"]):
        raise ArtifactMismatch("CLIP embedding size or input size differs from the manifest")
    return ClipEncoder(clip["model"], clip["pretrained"], bool(clip["quick_gelu"]), model, preprocess,
                       torch.device("cpu"))


def load_model(artifact_dir: Path, model_file: Path | None = None) -> ModelHandle:
    """Load and verify a bundle folder. model_file (e.g. RANKING_MODEL_PATH) must be the manifest's model file."""
    root = Path(artifact_dir)
    manifest = read_manifest(root)
    verify_files(root, manifest)
    if model_file is not None and Path(model_file).resolve() != safe_member(root, manifest["model_file"]).resolve():
        raise ArtifactMismatch("the configured model file is not the model file of this bundle")
    verify_packages(manifest)
    clip, stats = manifest["clip"], manifest["stats"]
    if manifest.get("method") != METHOD or clip.get("preprocessing_version") != PREPROCESSING_VERSION \
            or list(clip.get("pad_color", [])) != list(DEFAULT_PAD_COLOR) or stats.get("version") != STATS_VERSION:
        raise ArtifactMismatch("method or preprocessing differs from this code version")
    if manifest["feature_version"] != feature_version(clip, stats["version"]):
        raise ArtifactMismatch("feature_version does not match the CLIP and statistics settings")

    config = json.loads(safe_member(root, manifest["config_file"]).read_text(encoding="utf-8"))
    columns = list(manifest["feature_columns"])
    expected_columns = [f"clip_{i}" for i in range(int(clip["embedding_dim"]))] + list(stats["columns"])
    if (config.get("model_version"), config.get("feature_version"), config.get("feature_columns")) != \
            (manifest["model_version"], manifest["feature_version"], columns) or columns != expected_columns:
        raise ArtifactMismatch("model_config.json, manifest and feature order do not agree")
    tensors = load_numpy(str(safe_member(root, manifest["model_file"])))
    try:
        mean, std, weights = (tensors[k] for k in ("scaler_mean", "scaler_std", "weights"))
    except KeyError as error:
        raise ArtifactMismatch("model.safetensors lacks weights or scaler") from error
    for array in (mean, std, weights):
        if array.shape != (len(columns),) or not np.isfinite(array).all():
            raise ArtifactMismatch("model arrays must be finite and match the feature count")
    if (std <= 0).any():
        raise ArtifactMismatch("scaler_std must be positive")
    gap = float(manifest.get("close_call_score_gap", -1))
    if not (gap > 0 and math.isfinite(gap)):
        raise ArtifactMismatch("close_call_score_gap must be a positive number")
    return ModelHandle(
        model_version=manifest["model_version"], feature_version=manifest["feature_version"],
        preprocessing_version=clip["preprocessing_version"], method=manifest["method"], clip=MappingProxyType(dict(clip)),
        feature_columns=tuple(columns), close_call_score_gap=gap,
        _scaler_mean=_read_only(mean), _scaler_std=_read_only(std), _weights=_read_only(weights),
        _encoder=_load_encoder(root, clip))


def _open_ad(image_path: Path) -> Image.Image:
    """The final ad: an existing 1080x1350 PNG that is opaque RGB (RGBA allowed only if fully opaque)."""
    path = Path(image_path)
    name = path.name
    if not path.is_file():
        raise InvalidImage(f"ad image not found: {name}")
    try:
        with Image.open(path) as image:
            image.load()
            fmt, size, mode = image.format, image.size, image.mode
            if fmt != "PNG":
                raise InvalidImage(f"ad image is not a PNG: {name}")
            if size != AD_SIZE:
                raise InvalidImage(f"ad image must be 1080x1350, got {size[0]}x{size[1]}: {name}")
            if mode == "RGBA" and image.getchannel("A").getextrema() == (255, 255):
                return image.convert("RGB")
            if mode != "RGB":
                raise InvalidImage(f"ad image must be opaque RGB, got {mode}: {name}")
            return image.copy()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidImage(f"ad image cannot be decoded: {name}") from error


def extract_features(image_path: Path, model: ModelHandle) -> FeatureVector:
    """[CLIP embedding | brightness, contrast, saturation, n_colors] as in training, float64."""
    image = _open_ad(image_path)
    try:
        clip = model._encoder.encode([image], mode="pad")[0]
        stats = image_stats(image)
        vector = np.concatenate([clip, stats]).astype(np.float64)
    except Exception as error:  # noqa: BLE001 - any encoder failure is an inference failure
        raise InferenceFailure(f"feature extraction failed: {Path(image_path).name}") from error
    if vector.shape != (len(model.feature_columns),) or not np.isfinite(vector).all():
        raise InferenceFailure(f"features are not finite or have the wrong size: {Path(image_path).name}")
    vector.setflags(write=False)
    return vector


def _score(features: np.ndarray, model: ModelHandle) -> float:
    score = float(((features - model._scaler_mean) / model._scaler_std) @ model._weights)
    if not math.isfinite(score):
        raise InferenceFailure("score is not finite")
    return score


def score_ad(image_path: Path, model: ModelHandle) -> float:
    """Raw relative preference score (not a probability, not a CTR)."""
    return _score(extract_features(image_path, model), model)


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def rank_ads(items: list[RankInput], model: ModelHandle) -> dict:
    """Scores, ranks (score descending, ties by candidate_id) and the six pairwise values, in input order."""
    if len(items) != 4 or not all(isinstance(item, RankInput) for item in items):
        raise ValueError("rank_ads needs exactly four RankInput items")
    ids = [item.candidate_id for item in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != 4:
        raise ValueError("candidate_id values must be four different non-empty strings")
    scores = {item.candidate_id: score_ad(item.rendered_image_path, model) for item in items}
    order = sorted(ids, key=lambda i: (-scores[i], i))
    rank = {candidate: position + 1 for position, candidate in enumerate(order)}
    ordered_ids = sorted(ids)
    comparisons = [
        {"candidate_a_id": a, "candidate_b_id": b, "probability_a_preferred": _sigmoid(scores[a] - scores[b])}
        for n, a in enumerate(ordered_ids) for b in ordered_ids[n + 1:]
    ]
    return {
        "model_version": model.model_version,
        "feature_version": model.feature_version,
        "items": [{"candidate_id": i, "score": scores[i], "rank": rank[i]} for i in ids],
        "pairwise": {"method": model.method, "comparisons": comparisons},
    }
