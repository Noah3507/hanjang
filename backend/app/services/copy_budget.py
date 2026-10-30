"""Conservative persistent ceiling for a future explicitly authorized live test.
No raw prompts, facts, response text, or keys are written here.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid
from app.services.copy_contract import CopyFailure

MAX_COST = (6000 * .75 + 2048 * 4.5) / 1_000_000

class CopyBudget:
    def __init__(self, path: Path, max_requests=6, budget_usd=.1):
        self.path = path
        if not 0 <= max_requests <= 6 or not 0 <= budget_usd <= .1:
            raise ValueError('Budget exceeds approved limits')
        self.max_requests, self.budget_usd = max_requests, budget_usd

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix('.lock')
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise CopyFailure('COPY_BUDGET_BUSY') from None
        try:
            os.close(fd)
            data = json.loads(self.path.read_text()) if self.path.exists() else {'calls': []}
            # Legacy reservations also consume the limit; never silently reset history.
            import math
            if not isinstance(data.get('calls'), list) or any(not isinstance(c, dict)
                or not isinstance(c.get('id'), str) or not isinstance(c.get('cost_ceiling_usd'), (int,float))
                or not math.isfinite(c['cost_ceiling_usd']) or c['cost_ceiling_usd'] < 0 for c in data['calls']):
                raise CopyFailure('COPY_BUDGET_INVALID')
            yield data
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            lock.unlink(missing_ok=True)

    def reserve(self):
        with self.locked() as data:
            calls = data['calls']
            if len(calls) >= self.max_requests or sum(c['cost_ceiling_usd'] for c in calls) + MAX_COST > self.budget_usd:
                raise CopyFailure('COPY_BUDGET_EXCEEDED')
            call = uuid.uuid4().hex
            calls.append({'id': call, 'cost_ceiling_usd': MAX_COST, 'usage_known': False, 'state': 'reserved'})
            return call

    def dispatched(self, call):
        with self.locked() as data:
            next(c for c in data['calls'] if c['id'] == call)['state'] = 'dispatched'

    def failed(self, call, code):
        with self.locked() as data:
            record = next(c for c in data['calls'] if c['id'] == call)
            record.update(state='failed', error_code=code)

    def settle(self, call, inputs, outputs):
        with self.locked() as data:
            record = next(c for c in data['calls'] if c['id'] == call)
            record.update(cost_ceiling_usd=(inputs*.75+outputs*4.5)/1_000_000,
                          input_tokens=inputs, output_tokens=outputs, usage_known=True, state='completed')
