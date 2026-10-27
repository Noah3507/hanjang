"""Image preprocessing shared by training and inference.

Contract (RANKING_CONTRACT_V1_1): keep the whole ad visible. Resize with
the aspect ratio kept and pad to a square; never center-crop away text.
The pad color is a candidate value until it is agreed with A.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

PREPROCESSING_VERSION = "pad-square-v1"
DEFAULT_PAD_COLOR: tuple[int, int, int] = (255, 255, 255)


def load_rgb(path: Path, allow_alpha: bool = False) -> Image.Image:
    """Open an image as RGB. Final ads must be opaque unless allow_alpha."""
    with Image.open(path) as image:
        image.load()
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha and not allow_alpha:
            raise ValueError(f"expected an opaque image, got mode {image.mode}: {path}")
        return image.convert("RGB")


def pad_to_square(
    image: Image.Image, fill: tuple[int, int, int] = DEFAULT_PAD_COLOR
) -> Image.Image:
    """Center the image on a square canvas without cropping or resizing it."""
    image = image.convert("RGB")
    width, height = image.size
    side = max(width, height)
    canvas = Image.new("RGB", (side, side), fill)
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas
