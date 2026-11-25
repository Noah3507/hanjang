"""Additive v3 contract; v2 Candidate and four-strategy schemas stay unchanged."""
from datetime import datetime
from typing import Literal
from pydantic import Field
from app.schemas.upload import StrictModel
from app.schemas.copy import Copy
from app.schemas.rendering import Candidate, RenderError
from app.schemas.ranking import Ranking
from app.schemas.diagnostics import CandidateDiagnostics

Strategy = Literal['emotional','price','visual','brand']


class Promotion(StrictModel):
    original_price: str = Field(default='',max_length=40)
    discount_text: str = Field(default='',max_length=10)
    promotion_text: str = Field(default='',max_length=40)
    period_text: str = Field(default='',max_length=40)


class DesignRequest(StrictModel):
    expected_render_revision: int = Field(ge=1)
    expected_source_asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    expected_copy_key: str = Field(pattern=r'^[a-f0-9]{32}$')
    promotion: Promotion = Field(default_factory=Promotion)


class DesignSnapshot(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_snapshot: str = Field(pattern=r'^[a-f0-9]{64}$')


class DesignEdit(DesignSnapshot):
    expected_asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    ad_copy: Copy = Field(alias='copy')
    price_text: str = Field(max_length=40)


class DesignCandidate(Candidate):
    template_id: str
    design_name: str
    generation_revision: int
    edit_revision: int = 0
    original_price_text: str


class DesignResponse(StrictModel):
    job_id: str
    strategy: Strategy
    operation: Literal['designs_v3'] = 'designs_v3'
    status: Literal['pending','processing','completed','failed']
    revision: int = 0
    source_revision: int
    source_asset_id: str
    copy_key: str | None
    template_version: str
    style_snapshot: dict[str, dict] = Field(default_factory=dict)
    promotion: Promotion = Field(default_factory=Promotion)
    is_current: bool = False
    editing: bool = False
    snapshot: str | None = None
    mock_copy: bool
    candidates: list[DesignCandidate] = Field(default_factory=list)
    diagnostics: list[CandidateDiagnostics] = Field(default_factory=list)
    ranking: Ranking | None = None
    ranking_close_call_score_gap: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    ranking_status: Literal['pending','processing','completed','failed'] = 'pending'
    ranking_error: RenderError | None = None
    error: RenderError | None = None
    failed_templates: list[str] = Field(default_factory=list)
    failed_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    expires_at: datetime
