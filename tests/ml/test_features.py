"""Tests for image statistics, CLIP features and the feature cache. No download."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from ml.features.clip_features import ClipEncoder, feature_version, open_image
from ml.features.image_stats import STAT_NAMES, image_stats

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ads"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ml_extract_features.py"


@pytest.fixture(scope="module")
def encoder():
    return ClipEncoder.load("ViT-B-32", pretrained=None)  # random weights, no download


def test_stats_of_plain_images():
    white = image_stats(Image.new("RGB", (64, 64), (255, 255, 255)))
    assert white.tolist() == pytest.approx([1.0, 0.0, 0.0, 1 / 4096])
    red = image_stats(Image.new("RGB", (64, 64), (255, 0, 0)))
    assert red[2] == pytest.approx(1.0)  # fully saturated
    half = Image.new("L", (64, 64), 0)
    half.paste(255, (0, 0, 32, 64))
    assert image_stats(half.convert("RGB"))[1] == pytest.approx(0.5, abs=1e-3)  # max contrast
    assert len(STAT_NAMES) == 4


def test_transparent_pixels_become_the_pad_color(tmp_path):
    path = tmp_path / "cutout.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 0)).save(path)
    image, had_alpha = open_image(path)
    assert had_alpha and image.mode == "RGB"
    assert image.getpixel((0, 0)) == (255, 255, 255)
    Image.new("RGB", (8, 8), (10, 20, 30)).save(path)
    assert open_image(path)[1] is False


@pytest.mark.skipif(not FIXTURES.exists(), reason="shared ad fixtures not present")
def test_shared_ad_fixtures_give_finite_unit_embeddings(encoder):
    images = [open_image(p)[0] for p in sorted(FIXTURES.glob("*.png"))]
    assert len(images) == 4
    for mode in ("pad", "center_crop"):
        features = encoder.encode(images, mode=mode)
        assert features.shape == (4, encoder.metadata()["embedding_dim"])
        assert np.isfinite(features).all()
        assert np.linalg.norm(features, axis=1) == pytest.approx(np.ones(4), abs=1e-5)
    assert np.array_equal(encoder.encode(images), encoder.encode(images))  # deterministic


def test_unknown_mode_is_rejected(encoder):
    with pytest.raises(ValueError):
        encoder.encode([Image.new("RGB", (32, 32))], mode="stretch")


def test_feature_version_names_every_setting(encoder):
    version = feature_version(encoder.metadata(), "stats-v1")
    assert version == "ViT-B-32-None-gelu-pad-square-v1-stats-v1"


def _setup(tmp_path, missing=False):
    split_dir = tmp_path / "data/processed/splits/split-v1"
    split_dir.mkdir(parents=True)
    for ds, root in (("taste", "data/raw/taste"), ("creativeranking", "data/raw/creativeranking/images")):
        names = [f"{ds}_{i}.png" for i in range(4)]
        (tmp_path / root).mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(names):
            if not (missing and ds == "creativeranking" and i == 3):
                Image.new("RGB", (40 + 10 * i, 50), (60 * i, 100, 200)).save(tmp_path / root / name)
        pd.DataFrame({
            "image_a": [names[0], names[2]], "image_b": [names[1], names[3]], "split": ["train", "val"],
        }).to_parquet(split_dir / f"{ds}.parquet")


def _load_script():
    spec = importlib.util.spec_from_file_location("ml_extract_features", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cache_files_line_up_with_their_index(tmp_path):
    _setup(tmp_path)
    manifest = _load_script().main(["--pretrained", "none", "--batch-size", "3"], repo_root=tmp_path)
    out = tmp_path / "data/features" / manifest["feature_version"]
    for ds in ("taste", "creativeranking"):
        index = pd.read_parquet(out / f"{ds}_index.parquet")
        assert len(index) == 4 and index["row"].tolist() == [0, 1, 2, 3]
        assert np.load(out / f"{ds}_clip.npy").shape == (4, 512)
        assert np.load(out / f"{ds}_stats.npy").shape == (4, 4)
        crop_index = pd.read_parquet(out / f"{ds}_center_crop_index.parquet")
        assert set(crop_index["split"]) == {"val"} and len(crop_index) == 2
        assert np.load(out / f"{ds}_clip_center_crop.npy").shape == (2, 512)
    saved = json.loads((out / "manifest.json").read_text())
    assert saved["stats"]["columns"] == list(STAT_NAMES)
    assert saved["clip"]["normalized"] == "l2" and set(saved["code"]) == {"commit", "dirty"}


def test_missing_image_writes_nothing(tmp_path):
    _setup(tmp_path, missing=True)
    with pytest.raises(SystemExit):
        _load_script().main(["--pretrained", "none"], repo_root=tmp_path)
    assert not (tmp_path / "data/features").exists() or not any((tmp_path / "data/features").iterdir())
