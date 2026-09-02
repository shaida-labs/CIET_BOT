from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.responses import UTF8JSONResponse

from app.core.config import Settings


class DomainSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {
            "/api/v1/chat",
            "/api/v1/chat/stream",
            "/api/v1/feedback",
            "/api/v1/support/tickets",
        }:
            origin = request.headers.get("origin") or request.headers.get("referer")
            if (
                (not origin and self.settings.environment == "production")
                or (origin and not is_allowed_origin(origin, self.settings.allowed_widget_domains))
            ):
                return UTF8JSONResponse({"detail": "Unauthorized widget domain"}, status_code=403)
        return await call_next(request)


def is_allowed_origin(origin: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(origin if "://" in origin else f"https://{origin}")
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    hostname = (parsed.hostname or "").lower()
    return any(
        hostname == domain.lower().rstrip(".")
        or hostname.endswith(f".{domain.lower().rstrip('.')}")
        for domain in allowed_domains
    )
