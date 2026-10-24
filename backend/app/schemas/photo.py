from datetime import datetime
from typing import Literal
from pydantic import BaseModel
from app.schemas.upload import StrictModel


class PhotoSource(StrictModel):
    photo_source: Literal["original", "processed"]


class PhotoAsset(BaseModel):
    asset_id: str
    width: int
    height: int
    mime_type: Literal["image/jpeg", "image/png"]
    sha256: str


class PhotoResponse(BaseModel):
    job_id: str
    operation: Literal["photo_processing"] = "photo_processing"
    status: Literal["pending", "processing", "completed", "failed"]
    original: PhotoAsset
    processed: PhotoAsset | None = None
    photo_source: Literal["original", "processed"] = "original"
    warnings: list[str] = []
    expires_at: datetime
