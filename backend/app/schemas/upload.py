from datetime import datetime
from typing import Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Facts(StrictModel):
    store_name: str = Field(min_length=1, max_length=80)
    product_name: str = Field(min_length=1, max_length=80)
    price_text: str = Field(min_length=1, max_length=40)
    address: str | None = Field(default=None, max_length=200)
    instagram_handle: str | None = Field(default=None, max_length=80)

    @field_validator("*")
    @classmethod
    def preserve_valid_text(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.strip() or any(unicodedata.category(c) in {"Cc", "Cs"} for c in value)
        ):
            raise ValueError("공백만 입력하거나 제어 문자를 사용할 수 없습니다.")
        return value


class InputDraft(StrictModel):
    facts: Facts
    mood: Literal["warm", "minimal", "vivid", "premium"]


class SessionResponse(BaseModel):
    session_token: str
    expires_at: datetime


class UploadResponse(BaseModel):
    job_id: str
    asset_id: str
    width: int
    height: int
    mime_type: Literal["image/jpeg", "image/png"]
    sha256: str
    created_at: datetime
    expires_at: datetime


class DraftResponse(BaseModel):
    job_id: str
    status: Literal["pending"] = "pending"
    facts: Facts
    mood: Literal["warm", "minimal", "vivid", "premium"]
    expires_at: datetime
