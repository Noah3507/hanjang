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
    def __init__(self, path: Path):
        self.path = path

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
            yield data
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            lock.unlink(missing_ok=True)

    def reserve(self):
        with self.locked() as data:
            calls = data['calls']
            if len(calls) >= 6 or sum(c['cost_ceiling_usd'] for c in calls) + MAX_COST > .1:
                raise CopyFailure('COPY_BUDGET_EXCEEDED')
            call = uuid.uuid4().hex
            calls.append({'id': call, 'cost_ceiling_usd': MAX_COST, 'usage_known': False})
            return call

    def settle(self, call, inputs, outputs):
        with self.locked() as data:
            record = next(c for c in data['calls'] if c['id'] == call)
            record.update(cost_ceiling_usd=(inputs*.75+outputs*4.5)/1_000_000,
                          input_tokens=inputs, output_tokens=outputs, usage_known=True)
