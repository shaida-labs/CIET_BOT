import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.api.routes import admin, auth, chat, health, whatsapp
from app.core.config import get_settings
from app.core.domain_security import DomainSecurityMiddleware

settings = get_settings()
logger = structlog.get_logger()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(title=settings.app_name, version="2.0.0")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(DomainSecurityMiddleware, settings=settings)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts + ["*"] if settings.environment == "local" else settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.widget_origin, settings.admin_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CIET-Tenant"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_, exc: RateLimitExceeded):
    return JSONResponse({"detail": f"Rate limit exceeded: {exc.detail}"}, status_code=429)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("http_error", path=request.url.path, status_code=exc.status_code, detail=exc.detail)
    return JSONResponse({"detail": exc.detail, "status_code": exc.status_code}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error", path=request.url.path, errors=exc.errors())
    return JSONResponse({"detail": "Invalid request", "errors": exc.errors()}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(whatsapp.router, prefix="/api/v1")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
