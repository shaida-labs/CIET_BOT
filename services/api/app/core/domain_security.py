from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import Settings


class DomainSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/api/v1/chat", "/api/v1/feedback"}:
            origin = request.headers.get("origin") or request.headers.get("referer")
            if origin and not is_allowed_origin(origin, self.settings.allowed_widget_domains):
                return JSONResponse({"detail": "Unauthorized widget domain"}, status_code=403)
        return await call_next(request)


def is_allowed_origin(origin: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(origin if "://" in origin else f"https://{origin}")
    hostname = (parsed.hostname or "").lower()
    return any(hostname == domain.lower() or hostname.endswith(f".{domain.lower()}") for domain in allowed_domains)
