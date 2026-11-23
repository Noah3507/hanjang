"""Only the approved experiment may extend the existing ledger ceiling to 12."""
import json
import pytest
from app.services.copy_budget import CopyBudget
from app.services.copy_contract import CopyFailure

def test_phase3_opt_in_preserves_history_budget_and_twelve_call_limit(tmp_path):
    path=tmp_path/'synthetic-ledger.json'
    original=[{'id':str(i),'cost_ceiling_usd':.01628625 if i==0 else 0} for i in range(10)]
    path.write_text(json.dumps({'calls':original}))
    for count,budget,opt in [(12,.1,False),(13,.1,True),(12,.10001,True)]:
        with pytest.raises(ValueError):CopyBudget(path,count,budget,approved_phase3=opt)
    budget=CopyBudget(path,12,.1,approved_phase3=True)
    budget.reserve();budget.reserve()
    with pytest.raises(CopyFailure):budget.reserve()
    records=json.loads(path.read_text())['calls']
    assert len(records)==12 and records[:10]==original
    assert sum(c['cost_ceiling_usd'] for c in records)<=.1
