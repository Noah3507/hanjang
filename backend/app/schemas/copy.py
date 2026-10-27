"""S5a copy only: no rendered candidates, ranking, or B contract changes."""
from datetime import datetime
from typing import Literal
import unicodedata
from pydantic import Field, field_validator, model_validator
from app.schemas.upload import StrictModel, InputDraft, Facts

STRATEGIES = ('emotional', 'price', 'visual', 'brand')

class Copy(StrictModel):
    headline: str = Field(min_length=1, max_length=60)
    body: str = Field(max_length=160)
    cta: str = Field(max_length=30)

    @field_validator('*')
    @classmethod
    def plain_text(cls, value):
        if (value and not value.strip()) or any(unicodedata.category(c) in {'Cc', 'Cs'} for c in value) or '<' in value or '>' in value:
            raise ValueError('Plain text only; no whitespace-only or control characters')
        return value

class Variant(StrictModel):
    strategy: Literal['emotional', 'price', 'visual', 'brand']
    ad_copy: Copy = Field(alias='copy')

class Variants(StrictModel):
    variants: list[Variant] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def complete_distinct_strategies(self):
        if {v.strategy for v in self.variants} != set(STRATEGIES):
            raise ValueError('Each strategy must occur exactly once')
        if len({(v.ad_copy.headline, v.ad_copy.body, v.ad_copy.cta) for v in self.variants}) != 4:
            raise ValueError('Four strategies cannot have identical copies')
        return self

class CopyRequest(StrictModel):
    expected_asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    expected_input: InputDraft

class CopyError(StrictModel):
    code: str
    message: str
    retryable: bool = False

class Attempt(StrictModel):
    attempt: int
    provider: Literal['mock', 'openai']
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    reserved_unknown_cost_usd: float = 0
    latency_seconds: float
    error_code: str | None = None

class CopyResponse(StrictModel):
    job_id: str
    operation: Literal['copy_generation'] = 'copy_generation'
    status: Literal['pending', 'processing', 'completed', 'failed']
    status_url: str
    source_asset_id: str
    input_hash: str
    is_current: bool
    facts: Facts
    mood: str
    product_features: str | None
    use_address_for_copy: bool
    provider: Literal['mock', 'openai']
    model: str
    prompt_version: str = 'copy-v1'
    analysis_used: bool
    review_required: bool = True
    variants: list[Variant] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: CopyError | None = None
    expires_at: datetime
