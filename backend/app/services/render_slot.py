"""Single-server dispatch fencing; never time-reap a running worker."""
from dataclasses import dataclass
from threading import current_thread
from time import monotonic
import uuid

@dataclass
class Lease:
    token: str
    reserved_at: float
    abandoned: object
    started_at: float | None = None
    thread: object | None = None

class RenderSlot:
    # Methods are called under RenderStore's RLock (and publication locks).
    def __init__(self, clock=monotonic, dispatch_timeout=30):
        self.clock, self.dispatch_timeout = clock, dispatch_timeout
        self.lease = None

    def recover(self):
        lease=self.lease
        if lease and lease.started_at is None and self.clock()-lease.reserved_at >= self.dispatch_timeout:
            self.cancel(lease.token)

    def reserve(self, abandoned):
        if self.lease:raise RuntimeError('Slot already reserved')
        token=uuid.uuid4().hex
        self.lease=Lease(token,self.clock(),abandoned)
        return token

    def claim(self,token):
        self.recover()
        if not self.lease or self.lease.token!=token or self.lease.started_at is not None:return False
        self.lease.started_at=self.clock();self.lease.thread=current_thread()
        return True

    def owns(self,token):
        return bool(self.lease and self.lease.token==token and self.lease.started_at is not None)

    def cancel(self,token):
        # Cancellation is safe only before executor dispatch.
        if self.lease and self.lease.token==token and self.lease.started_at is None:
            lease=self.lease;self.lease=None
            lease.abandoned()

    def release(self,token):
        if self.lease and self.lease.token==token:self.lease=None
