"""Pinned, local-only rembg choices. Model provisioning is always explicit."""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import file_digest
from pathlib import Path


@dataclass(frozen=True)
class PhotoModel:
    name: str
    module: str
    session: str
    sha256: str
    size: int
    url: str
    upstream_md5: str


RELEASE = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/'
MODELS = {
    'u2netp': PhotoModel('u2netp', 'u2netp', 'U2netpSession',
        '309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8', 4574861,
        RELEASE+'u2netp.onnx', '8e83ca70e441ab06c318d82300c84806'),
    'u2net': PhotoModel('u2net', 'u2net', 'U2netSession',
        '8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491', 175997641,
        RELEASE+'u2net.onnx', '60024c5c889badc19c04ad937298a77b'),
    'birefnet-general-lite': PhotoModel('birefnet-general-lite', 'birefnet_general_lite', 'BiRefNetSessionGeneralLite',
        '5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333', 224005088,
        RELEASE+'BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx', '4fab47adc4ff364be1713e97b7e66334'),
}


def model_file_verified(path: Path, name: str) -> bool:
    """Local checksum check, never ONNX loading or provisioning.

    The cache binds file identity/metadata and the pinned digest. Inference
    independently verifies weights again when opening its offline session.
    """
    spec = MODELS.get(name)
    path = Path(path)
    try:
        if spec is None or path.is_symlink() or not path.is_file():
            return False
        stat = path.stat()
        if stat.st_size != spec.size:
            return False
        identity = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
        return _verified(str(path.resolve()), identity, spec.sha256)
    except OSError:
        return False


@lru_cache(maxsize=8)
def _verified(path, identity, expected):
    try:
        with Path(path).open('rb') as stream:
            checksum = file_digest(stream, 'sha256').hexdigest()
        stat = Path(path).stat()
        return checksum == expected and identity == (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    except OSError:
        return False
