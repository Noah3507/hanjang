"""Bounded deterministic K-means; never changes stored product pixels."""
from io import BytesIO
import numpy as np
from PIL import Image, ImageOps
from app.schemas.analysis import Palette, Color

def extract_palette(data: bytes) -> Palette:
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 24_000_000:
            raise ValueError('Image too large')
        rgba = np.asarray(ImageOps.exif_transpose(source).convert('RGBA'))
    pixels = rgba[:, :, :3][rgba[:, :, 3] >= 128]
    if len(pixels) == 0:
        return Palette()
    rng = np.random.default_rng(0)
    if len(pixels) > 4096:
        pixels = pixels[rng.choice(len(pixels), 4096, replace=False)]
    pixels = pixels.astype(np.float64)
    unique = np.unique(pixels, axis=0)
    k = min(5, len(unique))
    centers = [unique[rng.integers(len(unique))]]
    for _ in range(1, k):
        distance = np.min(((unique[:, None] - np.array(centers)) ** 2).sum(2), axis=1)
        centers.append(unique[rng.choice(len(unique), p=distance / distance.sum())])
    centers = np.array(centers)
    for _ in range(30):
        labels = ((pixels[:, None] - centers) ** 2).sum(2).argmin(1)
        updated = np.array([pixels[labels == i].mean(0) if (labels == i).any() else centers[i] for i in range(k)])
        if np.allclose(updated, centers):
            break
        centers = updated
    labels = ((pixels[:, None] - centers) ** 2).sum(2).argmin(1)
    counts: dict[tuple[int, int, int], int] = {}
    for i, center in enumerate(centers):
        count = int((labels == i).sum())
        if count:
            rgb = tuple(int(v) for v in np.rint(center).clip(0, 255))
            counts[rgb] = counts.get(rgb, 0) + count
    colors = [Color(hex='#%02X%02X%02X' % rgb, rgb=rgb, proportion=count / len(pixels))
              for rgb, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    return Palette(status='available', colors=colors, sampled_pixels=len(pixels))
