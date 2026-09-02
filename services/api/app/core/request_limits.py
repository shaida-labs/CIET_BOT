from app.core.responses import UTF8JSONResponse

from app.core.config import Settings


def body_limit_for(path: str, method: str, settings: Settings) -> int | None:
    if method not in {"POST", "PUT", "PATCH"}:
        return None
    if path == "/api/v1/admin/documents":
        return settings.max_upload_bytes + settings.multipart_overhead_bytes
    if path == "/api/v1/whatsapp/webhook":
        return settings.max_webhook_body_bytes
    if path.startswith("/api/"):
        return settings.max_json_body_bytes
    return None


class RequestSizeLimitMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            limit = body_limit_for(scope.get("path", ""), scope.get("method", "GET"), self.settings)
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            raw_length = headers.get(b"content-length")
            if limit is not None and raw_length:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    response = UTF8JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
                    await response(scope, receive, send)
                    return
                if content_length < 0 or content_length > limit:
                    response = UTF8JSONResponse({"detail": "Request body is too large"}, status_code=413)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
