"""CLIP image embeddings for the preference model (decided with A on 2026-10-27).

Encoder ViT-B-32 / openai, built with QuickGELU to match the weights, CPU,
input 224, open_clip's own resize/normalization. Images are padded to a
square first (pad-square-v1, white) so nothing is cropped. A "center_crop"
mode exists only for the padding-vs-crop comparison in evaluation.
Embeddings are L2-normalized float32.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image

from ml.clip_config import PRETRAINED_TAG, embedding_dim, input_size, uses_quick_gelu
from ml.features.preprocess import DEFAULT_PAD_COLOR, PREPROCESSING_VERSION, pad_to_square

DEFAULT_MODEL = "ViT-B-32"
MODES = ("pad", "center_crop")


def open_image(path: Path, background: tuple[int, int, int] = DEFAULT_PAD_COLOR) -> tuple[Image.Image, bool]:
    """Open any training image as RGB. Transparent areas are filled with the pad color.

    Returns (image, had_alpha). Final ads in the service are opaque, but some
    dataset images are not; flattening on the pad color keeps them consistent.
    """
    with Image.open(path) as image:
        image.load()
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        if not has_alpha:
            return image.convert("RGB"), False
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, background)
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas, True


@dataclass
class ClipEncoder:
    model_name: str
    pretrained: str | None
    quick_gelu: bool
    model: torch.nn.Module
    preprocess: object
    device: torch.device

    @classmethod
    def load(cls, model_name: str = DEFAULT_MODEL, pretrained: str | None = PRETRAINED_TAG,
             device: str = "cpu") -> "ClipEncoder":
        """pretrained=None builds random weights (tests only, no download)."""
        quick_gelu = pretrained is not None and uses_quick_gelu(model_name, pretrained)
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=device, force_quick_gelu=quick_gelu
        )
        model.eval()
        return cls(model_name, pretrained, quick_gelu, model, preprocess, torch.device(device))

    def metadata(self) -> dict:
        return {
            "model": self.model_name,
            "pretrained": self.pretrained,
            "quick_gelu": self.quick_gelu,
            "device": str(self.device),
            "input_size": input_size(self.model_name),
            "embedding_dim": embedding_dim(self.model_name),
            "preprocessing_version": PREPROCESSING_VERSION,
            "pad_color": list(DEFAULT_PAD_COLOR),
            "normalized": "l2",
            "open_clip": open_clip.__version__,
            "torch": torch.__version__,
        }

    def tensor(self, image: Image.Image, mode: str = "pad") -> torch.Tensor:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode}")
        if mode == "pad":
            image = pad_to_square(image, DEFAULT_PAD_COLOR)
        return self.preprocess(image)

    @torch.no_grad()
    def encode(self, images: Iterable[Image.Image], mode: str = "pad") -> np.ndarray:
        batch = torch.stack([self.tensor(image, mode) for image in images]).to(self.device)
        features = self.model.encode_image(batch).float()
        features = features / features.norm(dim=-1, keepdim=True)
        return features.cpu().numpy().astype(np.float32)


def feature_version(meta: dict, stats_version: str) -> str:
    """Folder name that changes whenever anything affecting the numbers changes."""
    gelu = "qg" if meta["quick_gelu"] else "gelu"
    return f"{meta['model']}-{meta['pretrained']}-{gelu}-{meta['preprocessing_version']}-{stats_version}"
