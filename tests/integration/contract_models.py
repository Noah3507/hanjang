"""Executable contract specification only; no serving or ML implementation."""
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.upload import Facts

Strategy = Literal["emotional", "price", "visual", "brand"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Copy(Contract):
    headline: str = Field(min_length=1, max_length=60)
    body: str = Field(max_length=160)
    cta: str = Field(max_length=30)


class Png(Contract):
    asset_id: str = Field(min_length=1)
    url: str = Field(pattern=r"^/api/v1/assets/[^/]+$")
    mime_type: Literal["image/png"]
    width: Literal[1080]
    height: Literal[1350]
    revision: int = Field(ge=1)


class TextBox(Contract):
    field: str
    text: str
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    font_size_px: float = Field(gt=0)
    font_weight: int
    foreground: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    background: str | None
    overflow: bool


class Box(Contract):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Renderer(Contract):
    template_version: str
    canvas_width: Literal[1080]
    canvas_height: Literal[1350]
    text_boxes: list[TextBox]
    product_bbox: Box
    photo_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    processed_photo_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Warning(Contract):
    code: str
    message: str


class Diagnostics(Contract):
    status: Literal["available", "partial", "unavailable"]
    rules_version: str
    min_font_size_px: float | None
    min_contrast_ratio: float | None
    text_overlap_ratio: float | None
    product_overlap_ratio: float | None
    layout_order: list[str] | None
    # Attention is optional product scope, intentionally unavailable in these fixtures.
    attention: None
    warnings: list[Warning]


class Candidate(Contract):
    candidate_id: str = Field(min_length=1)
    strategy: Strategy
    revision: int = Field(ge=1)
    facts: Facts
    ad_copy: Copy = Field(alias="copy")
    png: Png
    renderer: Renderer
    diagnostics: Diagnostics

    @model_validator(mode="after")
    def matching_revision_and_facts(self):
        if self.revision != self.png.revision:
            raise ValueError("PNG revision must match candidate")
        for key in ("store_name", "product_name", "price_text"):
            boxes = [box for box in self.renderer.text_boxes if box.field == key]
            if len(boxes) != 1 or boxes[0].text != getattr(self.facts, key):
                raise ValueError("Factual text must equal input exactly")
        return self


class CandidateSet(Contract):
    candidates: list[Candidate] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def four_distinct_candidates(self):
        if len({item.candidate_id for item in self.candidates}) != 4:
            raise ValueError("Four unique IDs required")
        if {item.strategy for item in self.candidates} != {"emotional", "price", "visual", "brand"}:
            raise ValueError("Four strategies required")
        if any(item.facts != self.candidates[0].facts or item.revision != self.candidates[0].revision for item in self.candidates):
            raise ValueError("Facts and revision must match across candidates")
        return self


class RankingItem(Contract):
    candidate_id: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=1, le=4)


class Preference(Contract):
    candidate_a_id: str
    candidate_b_id: str
    probability_a_preferred: float = Field(ge=0, le=1)


class Pairwise(Contract):
    method: Literal["bradley_terry_sigmoid_v1"]
    comparisons: list[Preference] = Field(min_length=6, max_length=6)


class Ranking(Contract):
    source: Literal["mock", "model", "fallback_mock"]
    model_version: str = Field(min_length=1)
    feature_version: str | None
    revision: int = Field(ge=1)
    items: list[RankingItem] = Field(min_length=4, max_length=4)
    pairwise: Pairwise | None = None

    @model_validator(mode="after")
    def verify_ranking(self):
        import math
        ids = [item.candidate_id for item in self.items]
        if len(set(ids)) != 4 or {item.rank for item in self.items} != {1, 2, 3, 4}:
            raise ValueError("Unique IDs and ranks 1..4 required")
        ordered = sorted(self.items, key=lambda item: (-item.score, item.candidate_id))
        if any(item.rank != i + 1 for i, item in enumerate(ordered)) or self.items != ordered:
            raise ValueError("HTTP items must be sorted by descending score, ties by ID")
        if self.source != "model":
            if self.pairwise is not None or self.feature_version is not None or self.model_version != "mock-v1":
                raise ValueError("Mock has no probabilities/features and uses mock-v1")
        elif not self.feature_version:
            raise ValueError("Model output needs a feature version")
        if self.pairwise:
            expected = set(combinations(sorted(ids), 2))
            actual = [(p.candidate_a_id, p.candidate_b_id) for p in self.pairwise.comparisons]
            if len(set(actual)) != 6 or set(actual) != expected:
                raise ValueError("Each unordered pair occurs once, IDs in lexical order")
            scores = {item.candidate_id: item.score for item in self.items}
            for pair in self.pairwise.comparisons:
                delta = scores[pair.candidate_a_id] - scores[pair.candidate_b_id]
                expected_probability = (1 / (1 + math.exp(-delta))) if delta >= 0 else math.exp(delta) / (1 + math.exp(delta))
                if not math.isclose(pair.probability_a_preferred, expected_probability, abs_tol=1e-6, rel_tol=0):
                    raise ValueError("Probability must match the declared score-difference method")
        return self


class RankOutput(Contract):
    """B batch result: input order, independent of HTTP display ordering."""
    model_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    items: list[RankingItem] = Field(min_length=4, max_length=4)
    pairwise: Pairwise | None = None

    @model_validator(mode="after")
    def validate_scores_and_pairs(self):
        Ranking.model_validate(dict(source="model", model_version=self.model_version,
            feature_version=self.feature_version, revision=1,
            items=[item.model_dump() for item in sorted(self.items, key=lambda item: item.rank)],
            pairwise=self.pairwise.model_dump() if self.pairwise else None))
        return self


def validate_batch_order(input_ids: list[str], output: RankOutput) -> None:
    if len(input_ids) != 4 or len(set(input_ids)) != 4 or input_ids != [item.candidate_id for item in output.items]:
        raise ValueError("B batch result must preserve all four input IDs in input order")


def validate_linkage(candidates: CandidateSet, ranking: Ranking) -> None:
    if {item.candidate_id for item in candidates.candidates} != {item.candidate_id for item in ranking.items}:
        raise ValueError("Ranking IDs must exactly match candidates")
    if any(item.revision != ranking.revision for item in candidates.candidates):
        raise ValueError("Ranking revision must match candidate revision")
