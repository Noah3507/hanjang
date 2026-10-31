"""Separate diagnostics contract: Candidate/B v1.1 remains unchanged."""
from datetime import datetime
from typing import Literal
import math
from pydantic import Field,field_validator,model_validator
from app.schemas.upload import StrictModel
from app.schemas.rendering import RenderError

class ExpectedCandidate(StrictModel):
    candidate_id: str = Field(min_length=1,max_length=128)
    asset_id: str = Field(pattern=r'^[a-f0-9]{32}$')

class DiagnosticsRequest(StrictModel):
    expected_render_revision: int = Field(ge=1)
    expected_candidates: list[ExpectedCandidate] = Field(min_length=4,max_length=4)
    @model_validator(mode='after')
    def unique(self):
        if len({c.candidate_id for c in self.expected_candidates})!=4 or len({c.asset_id for c in self.expected_candidates})!=4:
            raise ValueError('Four unique candidates and assets required')
        return self

Coverage=Literal['complete','partial','unavailable']
class RuleResult(StrictModel):
    rule_id: str
    status: Literal['normal','caution','problem','unavailable']
    coverage: Coverage
    measured_value: dict | None
    unit: str
    criterion: str
    explanation: str
    action: str
    @field_validator('measured_value')
    @classmethod
    def finite(cls,value):
        def check(v):
            if isinstance(v,float) and not math.isfinite(v):raise ValueError('Finite measurements only')
            if isinstance(v,dict):
                for x in v.values():check(x)
            if isinstance(v,list):
                for x in v:check(x)
        check(value);return value

class CandidateDiagnostics(StrictModel):
    candidate_id: str
    strategy: Literal['emotional','price','visual','brand']
    asset_id: str
    coverage: Coverage
    rules: list[RuleResult]

class DiagnosticsResponse(StrictModel):
    job_id: str
    operation: Literal['diagnostics']='diagnostics'
    status: Literal['pending','processing','completed','failed']='pending'
    revision: int | None=None
    is_current: bool=False
    rules_version: str
    results: list[CandidateDiagnostics]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)
    error: RenderError | None=None
    expires_at: datetime
