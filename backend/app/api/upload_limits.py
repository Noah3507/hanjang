from starlette.datastructures import Headers

from app.api.errors import error_response
from app.services.uploads import MAX_BYTES, UploadError


class UploadLimitMiddleware:
    """Bound request bytes before multipart parsing/spooling; reject unauthorized upload."""

    def __init__(self, app, storage):
        self.app, self.storage = app, storage

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        upload = scope.get("method") == "POST" and path == "/api/v1/uploads"
        draft = path.startswith("/api/v1/jobs/") and ((scope.get("method") == "PUT" and path.endswith(("/input", "/photo-source"))) or (scope.get("method") == "POST" and path.endswith(("/photo-processing", "/photo-analysis", "/copy-generation", "/rendering", "/ranking"))))
        edit = scope.get('method') == 'PATCH' and path.startswith('/api/v1/jobs/') and '/candidates/' in path
        if scope["type"] != "http" or not (upload or draft or edit):
            return await self.app(scope, receive, send)
        try:
            self.storage.authenticate(Headers(scope=scope).get("x-hanjang-session"))
        except UploadError as error:
            return await error_response(error.status, error.code, error.message)(scope, receive, send)
        maximum = MAX_BYTES + 65536 if upload else 16384
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > maximum:
                return await error_response(413, "FILE_TOO_LARGE", "요청 크기가 너무 큽니다.")(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        consumed = False
        async def limited_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        return await self.app(scope, limited_receive, send)
