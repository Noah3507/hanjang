"""Product-photo cues, separate from facts and B ranking."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.upload import StrictModel

class AnalysisRequest(StrictModel):
    expected_asset_id: str = Field(pattern=r"^[a-f0-9]{32}$")

class Cue(StrictModel):
    category: Literal['category', 'appearance', 'impression']
    candidate_id: str
    label: str
    similarity: float = Field(ge=-1, le=1, allow_inf_nan=False)

class ClipResult(StrictModel):
    status: Literal['available', 'unavailable'] = 'unavailable'
    model_version: str = 'ViT-B-32-openai-40d36571'
    prompt_version: str = 'product-cues-v1'
    preprocessing_version: str = 'product-white-pad-224-v1'
    score_type: Literal['cosine_similarity'] = 'cosine_similarity'
    cues: list[Cue] = Field(default_factory=list)

class Color(StrictModel):
    hex: str = Field(pattern=r'^#[0-9A-F]{6}$')
    rgb: tuple[int, int, int]
    proportion: float = Field(gt=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def check_rgb(self):
        if any(not 0 <= v <= 255 for v in self.rgb) or self.hex != '#%02X%02X%02X' % self.rgb:
            raise ValueError('RGB/HEX mismatch')
        return self

class Palette(StrictModel):
    status: Literal['available', 'unavailable'] = 'unavailable'
    method_version: str = 'rgb-kmeans-seed0-alpha128-v1'
    colors: list[Color] = Field(default_factory=list, max_length=5)
    sampled_pixels: int = Field(default=0, ge=0, le=4096)

    @model_validator(mode='after')
    def check_sum(self):
        if self.status == 'available' and (not self.colors or abs(sum(c.proportion for c in self.colors)-1) > 1e-6):
            raise ValueError('Palette proportions must sum to one')
        return self

class AnalysisError(StrictModel):
    code: str
    message: str

class AnalysisResponse(StrictModel):
    job_id: str
    operation: Literal['photo_analysis'] = 'photo_analysis'
    status: Literal['pending', 'processing', 'completed', 'failed']
    status_url: str
    source_asset_id: str
    photo_source: Literal['original', 'processed']
    is_current: bool
    analysis_version: str = 'product-analysis-v1'
    expires_at: datetime
    warnings: list[str] = Field(default_factory=list)
    error: AnalysisError | None = None
    clip: ClipResult = Field(default_factory=ClipResult)
    palette: Palette = Field(default_factory=Palette)
