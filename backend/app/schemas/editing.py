"""Additive service editing envelope; Candidate v1.1 is unchanged."""
from typing import Literal
from datetime import datetime
from pydantic import Field, model_validator
from app.schemas.rendering import RenderRequest, RenderError
from app.schemas.copy import Copy
from app.schemas.upload import StrictModel

class EditRequest(RenderRequest):
    expected_revision: int = Field(ge=1)
    expected_candidate_ids: list[str] = Field(min_length=4, max_length=4)
    ad_copy: Copy = Field(alias='copy')

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.expected_candidate_ids)) != 4:
            raise ValueError('Four unique candidate IDs required')
        return self

class EditResponse(StrictModel):
    job_id: str
    operation: Literal['editing'] = 'editing'
    status: Literal['pending', 'processing', 'completed', 'failed'] = 'pending'
    status_url: str
    edit_id: str | None = None
    candidate_id: str | None = None
    base_revision: int | None = None
    target_revision: int | None = None
    is_current: bool = False
    error: RenderError | None = None
    expires_at: datetime
