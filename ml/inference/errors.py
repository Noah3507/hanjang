"""Exceptions of the inference package (agreed with A on 2026-10-31).

Every error derives from RankingError, so the service adapter can catch one
type and fall back to MockRanker for all four candidates. Messages never
contain absolute paths or stack traces; at most a file name.
Calling mistakes (not exactly four candidates, duplicated IDs) are ValueError.
"""


class RankingError(Exception):
    """Base class of every inference failure the service adapter should handle."""


class ModelNotAvailable(RankingError):
    """The bundle folder, its manifest or a listed file is missing or cannot be read."""


class ArtifactMismatch(RankingError):
    """Checksum, size, version, dimension, column order or package version does not match the manifest."""


class InvalidImage(RankingError):
    """An ad image is missing, not a PNG, not decodable, not opaque RGB or not 1080x1350."""


class InferenceFailure(RankingError):
    """Encoding or scoring failed, or produced a non-finite value."""
