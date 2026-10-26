"""Select the compute device for the preference model.

Order: CUDA (NVIDIA GPU) -> MPS (Apple Silicon GPU) -> CPU.
Never hard-code ``device="cuda"``; teammates use macOS and Windows,
and CI runs on Ubuntu without a GPU.
"""

from __future__ import annotations

import torch


def select_device(preferred: str | None = None) -> torch.device:
    """Return the best available device, or ``preferred`` when given.

    Pass ``preferred="cpu"`` to force CPU, for example when checking
    that results match across machines.
    """
    if preferred is not None:
        return torch.device(preferred)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")