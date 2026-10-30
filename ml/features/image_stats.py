"""Simple, explainable image statistics used next to the CLIP embedding.

Computed on the original image (no padding, so the white margin does not
change the numbers), shrunk to at most 256 px for speed. Every value is in
[0, 1]. The order of STAT_NAMES is the column order of the saved matrix.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

STATS_VERSION = "stats-v1"
STAT_NAMES: tuple[str, ...] = ("brightness", "contrast", "saturation", "n_colors")
_MAX_SIDE = 256
_COLOR_LEVELS = 16  # 16 levels per channel -> 4096 possible colors


def image_stats(image: Image.Image) -> np.ndarray:
    """[brightness, contrast, saturation, n_colors] of an RGB image, each in [0, 1].

    brightness: mean luma; contrast: standard deviation of luma (0.5 at most);
    saturation: mean HSV saturation; n_colors: share of the 4096 coarse colors
    (16 levels per channel) that appear in the image.
    """
    small = image.convert("RGB")
    small.thumbnail((_MAX_SIDE, _MAX_SIDE))
    luma = np.asarray(small.convert("L"), dtype=np.float32) / 255.0
    saturation = np.asarray(small.convert("HSV"), dtype=np.float32)[..., 1] / 255.0
    coarse = np.asarray(small, dtype=np.uint16) // (256 // _COLOR_LEVELS)
    codes = (coarse[..., 0] * _COLOR_LEVELS + coarse[..., 1]) * _COLOR_LEVELS + coarse[..., 2]
    n_colors = np.unique(codes).size / float(_COLOR_LEVELS ** 3)
    return np.array(
        [luma.mean(), luma.std(), saturation.mean(), n_colors], dtype=np.float32
    )
