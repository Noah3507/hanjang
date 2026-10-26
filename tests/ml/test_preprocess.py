"""Tests for padding preprocessing. No model weights are downloaded."""

from pathlib import Path

import pytest
from PIL import Image

from ml.features.preprocess import DEFAULT_PAD_COLOR, load_rgb, pad_to_square

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ads"


def test_pad_keeps_every_original_pixel():
    image = Image.new("RGB", (1080, 1350), (10, 20, 30))
    image.putpixel((0, 0), (200, 0, 0))  # top-left corner
    image.putpixel((1079, 1349), (0, 200, 0))  # bottom-right corner
    padded = pad_to_square(image)
    assert padded.size == (1350, 1350)
    offset_x = (1350 - 1080) // 2
    assert padded.getpixel((offset_x, 0)) == (200, 0, 0)
    assert padded.getpixel((offset_x + 1079, 1349)) == (0, 200, 0)
    assert padded.getpixel((0, 675)) == DEFAULT_PAD_COLOR


def test_pad_square_image_is_unchanged_in_size():
    image = Image.new("RGB", (224, 224), (1, 2, 3))
    assert pad_to_square(image).size == (224, 224)


def test_pad_color_is_configurable():
    image = Image.new("RGB", (100, 50), (9, 9, 9))
    padded = pad_to_square(image, fill=(0, 0, 0))
    assert padded.getpixel((50, 0)) == (0, 0, 0)


def test_load_rgb_rejects_transparent_image(tmp_path):
    path = tmp_path / "cutout.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    with pytest.raises(ValueError):
        load_rgb(path)
    assert load_rgb(path, allow_alpha=True).mode == "RGB"


@pytest.mark.skipif(not FIXTURES.exists(), reason="shared ad fixtures not present")
def test_shared_ad_fixtures_pad_to_square():
    paths = sorted(FIXTURES.glob("*.png"))
    assert len(paths) == 4
    for path in paths:
        image = load_rgb(path)
        assert image.size == (1080, 1350)
        assert pad_to_square(image).size == (1350, 1350)
