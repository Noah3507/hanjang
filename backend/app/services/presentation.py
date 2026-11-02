"""Optional presentation-origin gateway. Existing session APIs remain unchanged."""
import base64
from collections import deque
from hashlib import sha256
import hmac
from threading import Lock
import time
from starlette.responses import JSONResponse


class PresentationGateway:
    def __init__(self,app,settings,clock=time.monotonic):
        password=settings.presentation_password.get_secret_value() if settings.presentation_password else ''
        if len(password)<20:raise ValueError('Presentation requires a server-only password of at least 20 characters.')
        self.app=app;self.clock=clock;self.lock=Lock()
        self.expected=sha256((settings.presentation_user+':'+password).encode()).digest()
        self.windows={name:deque() for name in ('failed_auth','requests','mutations')}
        self.limits={'failed_auth':20,'requests':settings.presentation_requests_per_minute,'mutations':settings.presentation_mutations_per_minute}

    def admitted(self,name):
        with self.lock:
            window=self.windows[name];now=self.clock()
            while window and window[0]<=now-60:window.popleft()
            if len(window)>=self.limits[name]:return False
            window.append(now);return True

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.lower():v for k,v in scope['headers']}
        try:
            auth=headers.get(b'authorization',b'').split(b' ',1)
            authenticated=auth[0].lower()==b'basic' and hmac.compare_digest(sha256(base64.b64decode(auth[1],validate=True)).digest(),self.expected)
        except (ValueError,IndexError):authenticated=False
        async def reject(status,code,message,extra=None):
            response=JSONResponse({'error':{'code':code,'message':message}},status_code=status,
                headers={'Cache-Control':'no-store',**(extra or {})})
            await response(scope,receive,send)
        if not authenticated:
            if not self.admitted('failed_auth'):return await reject(429,'PRESENTATION_RATE_LIMIT','Please wait and retry.',{'Retry-After':'60'})
            return await reject(401,'PRESENTATION_AUTH_REQUIRED','Presentation access is restricted.',{'WWW-Authenticate':'Basic realm="Hanjang presentation", charset="UTF-8"'})
        if not self.admitted('requests'):return await reject(429,'PRESENTATION_RATE_LIMIT','Please wait and retry.',{'Retry-After':'60'})
        if scope['method'] not in ('GET','HEAD','OPTIONS'):
            origin=headers.get(b'origin',b'').decode('latin1');host=headers.get(b'host',b'').decode('latin1')
            if origin and origin not in ('https://'+host,'http://'+host):
                return await reject(403,'PRESENTATION_ORIGIN_REJECTED','Cross-origin writes are not allowed.')
            if not self.admitted('mutations'):return await reject(429,'PRESENTATION_RATE_LIMIT','Please wait and retry.',{'Retry-After':'60'})
        async def secure_send(message):
            if message['type']=='http.response.start':
                message=dict(message);message['headers']=list(message.get('headers',[]))+[
                    (b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),(b'x-frame-options',b'DENY'),
                    (b'content-security-policy',b"default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")]
            await send(message)
        await self.app(scope,receive,secure_send)
