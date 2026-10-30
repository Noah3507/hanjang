"""Serving Ranking must continue to accept the existing v1.1 fixtures."""
import json
from pathlib import Path
import pytest
from app.schemas.ranking import Ranking
from contract_models import Ranking as ContractRanking


@pytest.mark.parametrize('name',['mock','model','fallback'])
def test_serving_matches_existing_contract(name):
    raw=json.loads(Path(f'tests/fixtures/contracts/ranking.{name}.json').read_text())
    assert Ranking.model_validate(raw).model_dump() == ContractRanking.model_validate(raw).model_dump()
