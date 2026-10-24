"""Non-generative alpha masking. Never modify original bytes or factual input."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from PIL import Image, ImageOps


class ModelUnavailable(Exception):
    pass


MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"


class LocalRembg:
    """Load only an explicitly provisioned model; no implicit network download."""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.session = None
        self.lock = Lock()

    def __call__(self, image: Image.Image) -> Image.Image:
        if not self.model_path.is_file() or self.model_path.is_symlink():
            raise ModelUnavailable()
        with self.lock:
            if self.session is None:
                if sha256(self.model_path.read_bytes()).hexdigest() != MODEL_SHA256:
                    raise ValueError("model checksum mismatch")
                from rembg.sessions.u2netp import U2netpSession
                from onnxruntime import SessionOptions
                path = self.model_path.resolve()

                class OfflineSession(U2netpSession):
                    @classmethod
                    def download_models(cls, *args, **kwargs):
                        return str(path)

                options = SessionOptions()
                options.intra_op_num_threads = 1
                self.session = OfflineSession("u2netp", options, providers=["CPUExecutionProvider"])
            # Mask only: rembg must never provide replacement RGB pixels.
            return self.session.predict(image)[0]


@dataclass
class ProcessedPhoto:
    png: bytes | None
    mask_png: bytes | None
    width: int
    height: int
    warnings: list[str]


def png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def process_photo(data: bytes, mask_provider, max_side: int = 1600) -> ProcessedPhoto:
    """Keep full frame, no upscaling/cropping/color correction. Size is configurable."""
    with Image.open(BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    width, height = image.size
    try:
        mask = mask_provider(image.convert("RGB"))
    except ModelUnavailable:
        return ProcessedPhoto(None, None, width, height, ["PHOTO_MODEL_UNAVAILABLE"])
    except Exception:
        return ProcessedPhoto(None, None, width, height, ["PHOTO_PROCESSING_FAILED"])
    if not isinstance(mask, Image.Image) or mask.size != image.size:
        return ProcessedPhoto(None, None, width, height, ["PHOTO_MASK_INVALID"])
    mask = mask.convert("L")
    alpha = np.minimum(np.asarray(mask), np.asarray(image.getchannel("A")))
    foreground = (alpha > 127).astype(np.uint8)
    count = int(cv2.countNonZero(foreground))
    if count == 0 or count == width * height:
        return ProcessedPhoto(None, None, width, height, ["PHOTO_MASK_INVALID"])
    # Heuristic warnings require manual inspection, not a product-damage verdict.
    warnings = []
    if count / (width * height) < 0.01 or count / (width * height) > 0.99:
        warnings.append("PHOTO_MASK_REVIEW_REQUIRED")
    image.putalpha(Image.fromarray(alpha))
    # Premultiplied-alpha resize avoids dark fringes while retaining aspect ratio.
    if max(width, height) > max_side:
        scale = max_side / max(width, height)
        dimensions = (max(1, round(width * scale)), max(1, round(height * scale)))
        image = image.convert("RGBa").resize(dimensions, Image.Resampling.LANCZOS).convert("RGBA")
        mask = Image.fromarray(alpha).resize(dimensions, Image.Resampling.LANCZOS)
    else:
        mask = Image.fromarray(alpha)
    return ProcessedPhoto(png_bytes(image), png_bytes(mask), *image.size, warnings)
