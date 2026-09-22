from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import admin, auth, chat, health, whatsapp
from app.core.config import get_settings
from app.core.domain_security import DomainSecurityMiddleware
from app.core.rate_limit import limiter
from app.core.request_limits import RequestSizeLimitMiddleware
from app.core.responses import UTF8JSONResponse
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.session import engine
from app.services.llm import close_openai_clients

settings = get_settings()
logger = structlog.get_logger()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_openai_clients()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)
app.add_middleware(DomainSecurityMiddleware, settings=settings)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CIET-Tenant", "X-CSRF-Token"],
)
app.add_middleware(RequestSizeLimitMiddleware, settings=settings)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_, exc: RateLimitExceeded):
    return UTF8JSONResponse({"detail": f"Rate limit exceeded: {exc.detail}"}, status_code=429)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("http_error", path=request.url.path, status_code=exc.status_code, detail=exc.detail)
    return UTF8JSONResponse({"detail": exc.detail, "status_code": exc.status_code}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = [
        {key: value for key, value in error.items() if key in {"type", "loc", "msg"}}
        for error in exc.errors()
    ]
    logger.warning("validation_error", path=request.url.path, errors=safe_errors)
    return UTF8JSONResponse({"detail": "Invalid request", "errors": safe_errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error", path=request.url.path, error_type=type(exc).__name__)
    return UTF8JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(whatsapp.router, prefix="/api/v1")

if settings.metrics_enabled:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
