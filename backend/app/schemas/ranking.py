"""Serving envelope around the unchanged Ranking v1.1 contract."""
from datetime import datetime
from itertools import combinations
import math
from typing import Literal
from pydantic import Field, model_validator
from app.schemas.upload import StrictModel


class RankingItem(StrictModel):
    candidate_id: str = Field(min_length=1)
    score: float = Field(allow_inf_nan=False)
    rank: int = Field(ge=1, le=4)


class Preference(StrictModel):
    candidate_a_id: str
    candidate_b_id: str
    probability_a_preferred: float = Field(ge=0, le=1, allow_inf_nan=False)


class Pairwise(StrictModel):
    method: Literal['bradley_terry_sigmoid_v1']
    comparisons: list[Preference] = Field(min_length=6, max_length=6)


class Ranking(StrictModel):
    source: Literal['mock', 'model', 'fallback_mock']
    model_version: str = Field(min_length=1)
    feature_version: str | None
    revision: int = Field(ge=1)
    items: list[RankingItem] = Field(min_length=4, max_length=4)
    pairwise: Pairwise | None = None

    @model_validator(mode='after')
    def contract(self):
        ids = [item.candidate_id for item in self.items]
        ordered = sorted(self.items, key=lambda item: (-item.score, item.candidate_id))
        if len(set(ids)) != 4 or self.items != ordered or any(item.rank != i+1 for i, item in enumerate(ordered)):
            raise ValueError('Four unique IDs, ordered finite scores and ranks 1..4 required')
        if self.source != 'model':
            if self.model_version != 'mock-v1' or self.feature_version is not None or self.pairwise is not None:
                raise ValueError('Mock has no model features or probabilities')
        elif not self.feature_version:
            raise ValueError('Model output requires feature version')
        if self.pairwise:
            pairs = [(p.candidate_a_id, p.candidate_b_id) for p in self.pairwise.comparisons]
            if len(set(pairs)) != 6 or set(pairs) != set(combinations(sorted(ids), 2)):
                raise ValueError('Exactly six distinct ordered pairs required')
            scores = {item.candidate_id: item.score for item in self.items}
            for pair in self.pairwise.comparisons:
                d = scores[pair.candidate_a_id] - scores[pair.candidate_b_id]
                p = 1/(1+math.exp(-d)) if d >= 0 else math.exp(d)/(1+math.exp(d))
                if not math.isclose(p, pair.probability_a_preferred, abs_tol=1e-6, rel_tol=0):
                    raise ValueError('Probability must match score difference')
        return self


class RankingRequest(StrictModel):
    expected_render_revision: int = Field(ge=1)
    expected_candidate_ids: list[str] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def distinct(self):
        if len(set(self.expected_candidate_ids)) != 4 or any(not value for value in self.expected_candidate_ids):
            raise ValueError('Four unique candidate IDs required')
        return self


class RankingError(StrictModel):
    code: str
    message: str


class RankingResponse(StrictModel):
    job_id: str
    operation: Literal['ranking'] = 'ranking'
    status: Literal['pending', 'processing', 'completed', 'failed']
    status_url: str
    revision: int | None = None
    is_current: bool = False
    ranking: Ranking | None = None
    warnings: list[str] = Field(default_factory=list)
    error: RankingError | None = None
    expires_at: datetime
