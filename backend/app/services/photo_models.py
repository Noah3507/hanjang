"""Pinned, local-only rembg choices. Model provisioning is always explicit."""
from dataclasses import dataclass


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
