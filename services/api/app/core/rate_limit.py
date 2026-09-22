from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    application_limits=[settings.rate_limit],
    headers_enabled=False,
    storage_uri=settings.redis_url if settings.environment != "local" else None,
    storage_options={"socket_connect_timeout": 1, "socket_timeout": 1},
    in_memory_fallback=[settings.rate_limit],
    in_memory_fallback_enabled=settings.environment != "local",
)
