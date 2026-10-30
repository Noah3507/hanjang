"""Deterministic demonstration values, never an image-quality measurement."""
from typing import Protocol
from app.schemas.ranking import Ranking
from app.schemas.rendering import Candidate

MOCK_NOTICE = '시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다'
STRATEGIES = {'emotional', 'price', 'visual', 'brand'}
DEMO_SCORES = {'visual': .8, 'emotional': .6, 'price': .4, 'brand': .2}


class Ranker(Protocol):
    def rank(self, candidates: list[Candidate], revision: int) -> Ranking: ...


def ordered_items(scores: list[tuple[str, float]]) -> list[dict]:
    # Ranking validates finite values, count, IDs and order before publication.
    return [dict(candidate_id=key, score=value, rank=i+1)
            for i, (key, value) in enumerate(sorted(scores, key=lambda item: (-item[1], item[0])))]


class MockRanker:
    def rank(self, candidates: list[Candidate], revision: int) -> Ranking:
        if len(candidates) != 4 or len({c.candidate_id for c in candidates}) != 4:
            raise ValueError('Four distinct candidates required')
        if {c.strategy for c in candidates} != STRATEGIES or any(c.revision != revision for c in candidates):
            raise ValueError('Strategies and revision must match')
        return Ranking(source='mock', model_version='mock-v1', feature_version=None, revision=revision,
            items=ordered_items([(c.candidate_id, DEMO_SCORES[c.strategy]) for c in candidates]), pairwise=None)
