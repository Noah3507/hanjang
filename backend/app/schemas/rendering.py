"""Rendering envelope; Candidate v1.1 fields stay unchanged."""
from datetime import datetime
from typing import Literal
from pydantic import Field
from app.schemas.upload import StrictModel, InputDraft, Facts
from app.schemas.copy import Copy

class Box(StrictModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)

class TextBox(Box):
    field: str
    text: str
    font_size_px: float = Field(gt=0)
    font_weight: int
    foreground: str
    background: str | None
    overflow: bool

class Renderer(StrictModel):
    template_version: str
    canvas_width: Literal[1080] = 1080
    canvas_height: Literal[1350] = 1350
    text_boxes: list[TextBox]
    product_bbox: Box
    photo_sha256: str
    processed_photo_sha256: str

class Png(StrictModel):
    asset_id: str
    url: str
    mime_type: Literal['image/png'] = 'image/png'
    width: Literal[1080] = 1080
    height: Literal[1350] = 1350
    revision: int

class Diagnostics(StrictModel):
    status: Literal['unavailable'] = 'unavailable'
    rules_version: str = 'renderer-no-diagnostics-v1'
    min_font_size_px: None = None
    min_contrast_ratio: None = None
    text_overlap_ratio: None = None
    product_overlap_ratio: None = None
    layout_order: None = None
    attention: None = None
    warnings: list = Field(default_factory=list)

class Candidate(StrictModel):
    candidate_id: str
    strategy: Literal['emotional', 'price', 'visual', 'brand']
    revision: int
    facts: Facts
    ad_copy: Copy = Field(alias='copy')
    png: Png
    renderer: Renderer
    diagnostics: Diagnostics = Field(default_factory=Diagnostics)

class RenderRequest(StrictModel):
    expected_asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    expected_input: InputDraft
    expected_copy_key: str = Field(pattern=r'^[a-f0-9]{32}$')

class RenderError(StrictModel):
    code: str
    message: str

class RenderResponse(StrictModel):
    job_id: str
    operation: Literal['rendering'] = 'rendering'
    status: Literal['pending', 'processing', 'completed', 'failed']
    status_url: str
    source_asset_id: str
    copy_key: str | None
    revision: int
    is_current: bool
    mock_copy: bool
    candidates: list[Candidate] = Field(default_factory=list)
    measurements: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: RenderError | None = None
    expires_at: datetime
