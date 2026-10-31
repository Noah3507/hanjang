"""Model bundle: manifest format, writing and verification (no pandas, no network).

A bundle is one folder, e.g. artifacts/models/ranking/bt-logistic-v1/:
  manifest.json                         this format (manifest_version ranking-bundle-v1)
  model.safetensors                     Bradley-Terry weights + scaler (written by scripts/ml_train.py)
  model_config.json                     feature order and versions (written by scripts/ml_train.py)
  clip/<model>-<pretrained>-visual.safetensors   the CLIP image tower, so nothing is downloaded at run time
Every listed file has its SHA-256 and size in the manifest. The manifest does
not contain its own hash.
"""

from __future__ import annotations

import hashlib
import json
from importlib import metadata
from pathlib import Path, PurePosixPath

from ml.inference.errors import ArtifactMismatch, ModelNotAvailable

MANIFEST_VERSION = "ranking-bundle-v1"
METHOD = "bradley_terry_sigmoid_v1"
PACKAGES = ("torch", "open_clip_torch", "pillow", "numpy", "safetensors")
CLOSE_CALL_SCORE_GAP = 0.2  # agreed with A on 2026-10-31 from CreativeRanking val score gaps


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def installed_versions() -> dict[str, str]:
    """Public versions of the packages that change the numbers (local tags like +cu130 dropped)."""
    return {name: metadata.version(name).split("+")[0] for name in PACKAGES}


def describe_file(root: Path, relative: str) -> dict:
    path = root / relative
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}


def safe_member(root: Path, relative: str) -> Path:
    """A listed file must stay inside the bundle folder (no absolute paths, no '..')."""
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or not relative:
        raise ArtifactMismatch(f"manifest lists a file outside the bundle: {relative!r}")
    return root / Path(*pure.parts)


def read_manifest(root: Path) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise ModelNotAvailable("model bundle folder not found")
    path = root / "manifest.json"
    if not path.is_file():
        raise ModelNotAvailable("manifest.json not found in the model bundle")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise ModelNotAvailable("manifest.json cannot be read") from error
    except json.JSONDecodeError as error:
        raise ArtifactMismatch("manifest.json is not valid JSON") from error
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ArtifactMismatch(f"unsupported manifest_version (expected {MANIFEST_VERSION})")
    return manifest


def verify_files(root: Path, manifest: dict) -> None:
    """Every listed file exists, stays inside the bundle and matches its size and SHA-256."""
    files = manifest.get("files")
    required = {manifest.get("model_file"), manifest.get("config_file"), manifest.get("clip", {}).get("weights_file")}
    if not isinstance(files, dict) or None in required or not required <= set(files):
        raise ArtifactMismatch("manifest must list the model, config and CLIP weight files")
    for relative, expected in files.items():
        path = safe_member(root, relative)
        if not path.is_file():
            raise ModelNotAvailable(f"bundle file missing: {PurePosixPath(relative).name}")
        if path.stat().st_size != expected.get("bytes") or sha256_file(path) != expected.get("sha256"):
            raise ArtifactMismatch(f"checksum or size mismatch: {PurePosixPath(relative).name}")


def verify_packages(manifest: dict) -> None:
    expected = manifest.get("packages", {})
    actual = installed_versions()
    wrong = {name: (expected.get(name), actual[name]) for name in PACKAGES if expected.get(name) != actual[name]}
    if wrong:
        detail = ", ".join(f"{n} {e} expected, {a} installed" for n, (e, a) in sorted(wrong.items()))
        raise ArtifactMismatch(f"package versions differ from the bundle: {detail}")


def write_manifest(root: Path, model_config: dict, clip: dict, code: dict | None = None) -> dict:
    """Write manifest.json for files already placed in root (model, config, CLIP weights)."""
    root = Path(root)
    files = ["model.safetensors", "model_config.json", clip["weights_file"]]
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "model_version": model_config["model_version"],
        "feature_version": model_config["feature_version"],
        "preprocessing_version": clip["preprocessing_version"],
        "method": METHOD,
        "score": "raw score s = sum(weights * (features - scaler_mean) / scaler_std); higher = preferred",
        "pairwise": "probability_a_preferred = sigmoid(s_a - s_b), temperature 1; a relative model value, "
                    "not a calibrated probability or a CTR prediction",
        "close_call_score_gap": CLOSE_CALL_SCORE_GAP,
        "model_file": "model.safetensors",
        "config_file": "model_config.json",
        "clip": clip,
        "stats": model_config["stats"],
        "feature_columns": model_config["feature_columns"],
        "image": {"format": "PNG", "mode": "opaque RGB", "size": [1080, 1350]},
        "packages": installed_versions(),
        "files": {name: describe_file(root, name) for name in files},
        "code": code,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def write_bundle(source_dir: Path, out_dir: Path, encoder, code: dict | None = None) -> dict:
    """Copy the trained model files into out_dir, add the CLIP image tower and write the manifest.

    encoder is an ml.features.clip_features.ClipEncoder with the weights used in training.
    Only the image tower is saved (the text tower is never used for ranking).
    """
    import shutil

    from safetensors.torch import save_file

    from ml.features.clip_features import feature_version
    from ml.features.preprocess import DEFAULT_PAD_COLOR, PREPROCESSING_VERSION

    source_dir, out_dir = Path(source_dir), Path(out_dir)
    for name in ("model.safetensors", "model_config.json", "training_report.json"):
        if (source_dir / name).exists():
            shutil.copy2(source_dir / name, out_dir / name)
    model_config = json.loads((out_dir / "model_config.json").read_text(encoding="utf-8"))
    meta = encoder.metadata()
    weights_file = f"clip/{meta['model']}-{meta['pretrained']}-visual.safetensors"
    (out_dir / "clip").mkdir(exist_ok=True)
    state = {k: v.detach().cpu().contiguous().clone() for k, v in encoder.model.visual.state_dict().items()}
    save_file(state, str(out_dir / weights_file))
    clip = {"model": meta["model"], "pretrained": meta["pretrained"], "quick_gelu": meta["quick_gelu"],
            "input_size": meta["input_size"], "embedding_dim": meta["embedding_dim"],
            "preprocessing_version": PREPROCESSING_VERSION, "pad_color": list(DEFAULT_PAD_COLOR),
            "normalized": "l2", "weights_file": weights_file, "tower": "visual"}
    if feature_version(clip, model_config["stats"]["version"]) != model_config["feature_version"]:
        raise ArtifactMismatch("the CLIP encoder does not match the feature version of the trained model")
    return write_manifest(out_dir, model_config, clip, code)
