"""Alpha cleanup after background removal: drop faint haze and pixels far from any solid part.

The model sometimes leaves grey half-transparent residue (table shadows, steam, the edge of the
backdrop, a half-erased plate). Templates now show the cut-out without a box behind it, so the
residue would show. Only alpha changes; colour pixels are never touched. Separate solid pieces
(alpha >= 128) all stay. Based on B's reported 11-photo comparison with
scripts/ml_cutout_haze.py ("both"); this is not semantic product segmentation.
"""
from __future__ import annotations

import cv2
import numpy as np

MATTE_VERSION = 'matte-cleanup-v1-preserve-solid'
SOLID_ALPHA = 128     # mask anchor confidence, not proof of real product identity
FAINT_ALPHA = 64      # below: transparent
NEAR_FRACTION = 0.03  # kept zone: within 3 % of the product's longer side from a solid part
MIN_PIECE = 0.01      # small pieces are not zone anchors; their solid alpha is still retained


def solid_core(alpha: np.ndarray) -> np.ndarray:
    solid = (alpha >= SOLID_ALPHA).astype(np.uint8)
    if not solid.size:
        return solid.astype(bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    if count <= 1:
        return solid.astype(bool)
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = [i + 1 for i, area in enumerate(areas) if area >= MIN_PIECE * areas.sum()]
    return np.isin(labels, keep)


def near_zone(core: np.ndarray, radius: int) -> np.ndarray:
    """Exact same ellipse dilation, with rectangular decomposition for large radii.

    An ellipse is the union of centered rectangles defined by its row spans;
    dilation distributes over that union. Rectangular OpenCV dilation is much
    cheaper than a large nonseparable ellipse on full-resolution uploads.
    """
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1))
    source=core.astype(np.uint8)
    if radius<=16:
        return cv2.dilate(source,kernel).astype(bool)
    spans=kernel.sum(axis=1)
    zone=np.zeros_like(source);work=np.empty_like(source)
    for width in np.unique(spans):
        height=int(np.count_nonzero(spans>=width))
        rectangle=cv2.getStructuringElement(cv2.MORPH_RECT,(int(width),height))
        cv2.dilate(source,rectangle,dst=work)
        cv2.bitwise_or(zone,work,dst=zone)
    return zone.astype(bool)


def clean_alpha(alpha: np.ndarray) -> np.ndarray:
    """Same shape and dtype; returns the input unchanged when there is no solid part to anchor to."""
    alpha = np.asarray(alpha, dtype=np.uint8)
    if alpha.ndim != 2:
        raise ValueError('Expected a two-dimensional alpha mask')
    if not alpha.size:
        return alpha.copy()
    core = solid_core(alpha)
    # Bounding-box extrema only: avoid two image-sized coordinate arrays on
    # large uploads. This gives exactly the same size/radius as np.nonzero.
    ys = np.flatnonzero(core.any(axis=1))
    xs = np.flatnonzero(core.any(axis=0))
    if len(xs) == 0:
        return alpha.copy()
    size = max(xs.max() - xs.min(), ys.max() - ys.min()) + 1
    radius = max(2, int(round(size * NEAR_FRACTION)))
    zone = near_zone(core, radius)
    # A tiny opaque component may be a genuine separated food/accessory piece.
    # Area alone cannot prove it is noise; preserve every >=128 pixel exactly.
    return np.where((alpha >= SOLID_ALPHA) | (zone & (alpha >= FAINT_ALPHA)), alpha, 0).astype(np.uint8)
