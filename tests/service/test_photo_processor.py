from io import BytesIO
from hashlib import sha256

import numpy as np
from PIL import Image

from app.services.photo_processor import LocalRembg, process_photo


def original(size=(320, 256)):
    stream = BytesIO()
    Image.new("RGB", size, (123, 65, 210)).save(stream, "PNG")
    return stream.getvalue()


def half_mask(image):
    mask = Image.new("L", image.size, 0)
    mask.paste(255, (0, 0, image.width // 2, image.height))
    return mask


def test_rgb_original_and_alpha_preserved():
    data = original()
    checksum = sha256(data).hexdigest()
    result = process_photo(data, half_mask)
    output = np.asarray(Image.open(BytesIO(result.png)))
    assert np.all(output[:, :, :3] == [123, 65, 210])
    assert np.all(output[:, :160, 3] == 255)
    assert np.all(output[:, 160:, 3] == 0)
    assert sha256(data).hexdigest() == checksum
    assert not result.warnings


def test_resize_keeps_frame_ratio_and_does_not_upscale():
    result = process_photo(original((2048, 1024)), half_mask)
    assert (result.width, result.height) == (1600, 800)
    assert process_photo(original(), half_mask).width == 320


def test_empty_full_wrong_size_and_provider_failure_fallback():
    for provider in [lambda image: Image.new("L", image.size, 0),
                     lambda image: Image.new("L", image.size, 255),
                     lambda image: Image.new("L", (1, 1)),
                     lambda image: None]:
        result = process_photo(original(), provider)
        assert result.png is None and result.warnings == ["PHOTO_MASK_INVALID"]
    def failure(image):
        raise RuntimeError("private path must not escape")
    result = process_photo(original(), failure)
    assert result.png is None and result.warnings == ["PHOTO_PROCESSING_FAILED"]


def test_model_missing_never_downloads(tmp_path):
    result = process_photo(original(), LocalRembg(tmp_path / "absent.onnx"))
    assert result.png is None and result.warnings == ["PHOTO_MODEL_UNAVAILABLE"]
    assert not list(tmp_path.iterdir())


def test_existing_alpha_is_not_restored():
    image = Image.new("RGBA", (320, 256), (123, 65, 210, 0))
    stream = BytesIO()
    image.save(stream, "PNG")
    assert process_photo(stream.getvalue(), half_mask).png is None


def test_tiny_mask_warns_and_corrupt_model_falls_back(tmp_path):
    def tiny(image):
        mask = Image.new("L", image.size, 0)
        mask.putpixel((0, 0), 255)
        return mask
    assert process_photo(original(), tiny).warnings == ["PHOTO_MASK_REVIEW_REQUIRED"]
    path = tmp_path / "corrupt.onnx"
    path.write_bytes(b"not a model")
    assert process_photo(original(), LocalRembg(path)).warnings == ["PHOTO_PROCESSING_FAILED"]


def test_exif_orientation_is_display_only_and_original_bytes_unchanged():
    stream = BytesIO()
    image = Image.new("RGB", (320, 256), (123, 65, 210))
    exif = image.getexif()
    exif[274] = 6
    image.save(stream, "JPEG", exif=exif)
    data = stream.getvalue()
    result = process_photo(data, half_mask)
    assert (result.width, result.height) == (256, 320)
    assert Image.open(BytesIO(data)).getexif()[274] == 6
