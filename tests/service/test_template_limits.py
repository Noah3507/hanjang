"""templates/v3/limits.json: the measured text limits of every template slot (B).

The static checks run in CI. Changing a template's HTML or CSS changes source_sha256, so the
saved limits must be re-measured (scripts/ml_measure_template_limits.py) in the same PR.
The render checks need Chromium (RUN_RENDER_TESTS=1).
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from app.services.template_v3 import REGISTRY, VERSION

ROOT = Path(__file__).resolve().parents[2]
LIMITS = json.loads((ROOT / 'templates/v3/limits.json').read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('measure_limits', ROOT / 'scripts/ml_measure_template_limits.py')
measure = importlib.util.module_from_spec(spec)
sys.modules['measure_limits'] = measure
spec.loader.exec_module(measure)
COPY = ('headline', 'body', 'cta')


def test_limits_were_measured_on_the_current_templates():
    assert LIMITS['source_sha256'] == measure.source_hash(), \
        'templates/v3 changed: run .venv/bin/python scripts/ml_measure_template_limits.py'
    assert LIMITS['template_version'] == VERSION


def test_every_template_and_strategy_is_covered():
    assert set(LIMITS['templates']) == {t for t, v in REGISTRY.items() if v['implemented']}
    assert set(LIMITS['strategies']) == {v['strategy'] for v in REGISTRY.values()}
    for template in LIMITS['templates'].values():
        for field, value in template.items():
            assert 0 < value['soft'] <= value['hard'], field


def test_strategy_limits_are_the_tightest_of_its_four_templates():
    for strategy, limits in LIMITS['strategies'].items():
        ids = [t for t, v in REGISTRY.items() if v['strategy'] == strategy]
        for field in COPY:
            for kind in ('soft', 'hard'):
                assert limits[field][kind] == min(LIMITS['templates'][t][field][kind] for t in ids)


def test_contract_names_the_fixed_slots_and_empty_fields():
    assert LIMITS['fixed_slots']['fields'] == ['store_name', 'product_name', 'price_text']
    assert LIMITS['empty_allowed'] == {**LIMITS['empty_allowed'], 'headline': False, 'body': True, 'cta': True}


def test_sample_text_has_the_asked_length_and_no_edge_spaces():
    for n in range(1, 120):
        text = measure.text_of(n)
        assert len(text) == n and text == text.strip()


@pytest.mark.skipif(os.getenv('RUN_RENDER_TESTS') != '1', reason='Explicit installed Chromium opt-in')
@pytest.mark.parametrize('strategy', sorted(LIMITS['strategies']))
def test_copy_at_the_strategy_limits_renders_in_all_four(strategy):
    """Soft length: no template of the strategy shrinks the field. Hard length: still renders, readable."""
    m = measure.Measurer()
    ids = [t for t in m.ids if REGISTRY[t]['strategy'] == strategy]
    for field in COPY:
        soft, hard = (LIMITS['strategies'][strategy][field][k] for k in ('soft', 'hard'))
        assert set(m.outcome(field, soft, ids).values()) == {'soft'}, (field, soft)
        assert 'no' not in set(m.outcome(field, hard, ids).values()), (field, hard)
