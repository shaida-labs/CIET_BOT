import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def discover_project_root(api_root: Path) -> Path:
    return next(
        (
            candidate
            for candidate in (api_root, *api_root.parents)
            if (candidate / "package.json").is_file()
        ),
        api_root,
    )


API_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = discover_project_root(API_ROOT)
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_JWT_SECRET = "local-development-only-change-me-32"


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.casefold().strip()
    return normalized.startswith(("replace-", "change-me", "example", "test-"))


def is_weak_secret(value: str | None, minimum_length: int) -> bool:
    return is_placeholder(value) or len(value or "") < minimum_length


class Settings(BaseSettings):
    # get_settings() opts into the repository .env file. Keeping the model itself
    # environment-only makes direct construction deterministic in tests and tools.
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    app_name: str = "CIET AI Assistant API"
    environment: Literal["local", "staging", "production"] = "local"
    api_base_url: AnyHttpUrl | str = "http://localhost:8000"
    widget_origin: str = "http://localhost:5173"
    admin_origin: str = "http://localhost:5174"
    cors_origins_extra: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    allowed_widget_domains: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    trusted_proxy_ips: list[str] = Field(default_factory=lambda: ["127.0.0.1"])

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ciet_ai"
    database_pool_size: int = Field(default=10, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout: int = Field(default=10, ge=1, le=60)
    database_command_timeout: int = Field(default=20, ge=1, le=120)
    jwt_secret: str = Field(default=DEFAULT_JWT_SECRET, min_length=32)
    jwt_issuer: str = "ciet-ai"
    jwt_audience: str = "ciet-admin"
    access_token_minutes: int = Field(default=30, ge=5, le=480)
    csrf_cookie_domain: str | None = None
    password_reset_minutes: int = Field(default=30, ge=5, le=1440)
    invitation_expiry_hours: int = Field(default=168, ge=1, le=720)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_mini_model: str = "gpt-5.6-luna"
    embedding_model: str = "text-embedding-3-large"
    openai_timeout_seconds: float = Field(default=25.0, gt=0, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=5)

    pinecone_api_key: str | None = None
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_index: str = "ciet-knowledge"
    pinecone_namespace: str = "ciet"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    multipart_overhead_bytes: int = Field(default=1024 * 1024, ge=64 * 1024, le=5 * 1024 * 1024)
    max_json_body_bytes: int = Field(default=64 * 1024, ge=4096, le=1024 * 1024)
    max_webhook_body_bytes: int = Field(default=1024 * 1024, ge=4096, le=5 * 1024 * 1024)
    clamav_host: str | None = None
    clamav_port: int = 3310

    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "ciet-ai-documents"
    local_storage_path: str = str(Path(__file__).resolve().parents[2] / "storage" / "uploads")

    whatsapp_verify_token: str = "change-me"
    whatsapp_app_secret: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None

    sentry_dsn: str | None = None
    rate_limit: str = "80/minute"
    auth_rate_limit: str = "10/minute"
    chat_rate_limit: str = "30/minute"
    expose_metrics: bool | None = None
    expose_api_docs: bool | None = None
    rag_top_k: int = Field(default=4, ge=1, le=10)
    rag_min_score: float = Field(default=0.34, ge=0, le=1)
    rag_high_confidence_score: float = Field(default=0.72, ge=0, le=1)
    conversation_memory_messages: int = Field(default=8, ge=0, le=20)
    conversation_memory_characters: int = Field(default=6000, ge=0, le=12000)
    response_cache_seconds: int = Field(default=0, ge=0, le=3600)
    official_website_url: AnyHttpUrl | str | None = None
    website_search_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    website_search_max_bytes: int = Field(default=1024 * 1024, ge=64 * 1024, le=5 * 1024 * 1024)

    safe_fallback: str = (
        "I could not find verified CIET information for this question. "
        "Rather than guess, please contact the CIET help desk for an official answer."
    )

    @field_validator(
        "allowed_hosts", "allowed_widget_domains", "trusted_proxy_ips", "cors_origins_extra", mode="before"
    )
    @classmethod
    def parse_csv_lists(cls, value):
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return decoded
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment != "production":
            return self
        errors: list[str] = []
        if (
            self.jwt_secret == DEFAULT_JWT_SECRET
            or len(self.jwt_secret) < 64
            or len(set(self.jwt_secret)) < 10
            or is_placeholder(self.jwt_secret)
        ):
            errors.append("JWT_SECRET must be a unique high-entropy value of at least 64 characters")
        if is_weak_secret(self.openai_api_key, 20):
            errors.append("OPENAI_API_KEY is required in production")
        if not self.clamav_host:
            errors.append("CLAMAV_HOST is required in production when document uploads are enabled")
        smtp_values = {
            "SMTP_HOST": self.smtp_host,
            "SMTP_USERNAME": self.smtp_username,
            "SMTP_PASSWORD": self.smtp_password,
            "SMTP_FROM": self.smtp_from,
        }
        missing_smtp = [name for name, value in smtp_values.items() if is_placeholder(value)]
        if missing_smtp:
            errors.append(f"Password-reset email requires: {', '.join(missing_smtp)}")
        whatsapp_values = {
            "WHATSAPP_VERIFY_TOKEN": self.whatsapp_verify_token,
            "WHATSAPP_APP_SECRET": self.whatsapp_app_secret,
            "WHATSAPP_ACCESS_TOKEN": self.whatsapp_access_token,
            "WHATSAPP_PHONE_NUMBER_ID": self.whatsapp_phone_number_id,
        }
        missing_whatsapp = [
            name for name, value in whatsapp_values.items() if is_weak_secret(value, 12)
        ]
        if missing_whatsapp:
            errors.append(f"WhatsApp integration requires: {', '.join(missing_whatsapp)}")
        if "*" in self.allowed_hosts:
            errors.append("ALLOWED_HOSTS cannot contain '*' in production")
        if "*" in self.trusted_proxy_ips:
            errors.append("TRUSTED_PROXY_IPS cannot contain '*' in production")
        if not self.allowed_hosts or all(host in {"localhost", "127.0.0.1"} for host in self.allowed_hosts):
            errors.append("ALLOWED_HOSTS must include the production API hostname")
        if any(
            not str(url).startswith("https://")
            for url in (self.api_base_url, self.widget_origin, self.admin_origin)
        ):
            errors.append("API_BASE_URL, WIDGET_ORIGIN, and ADMIN_ORIGIN must use HTTPS in production")
        if self.official_website_url and not str(self.official_website_url).startswith("https://"):
            errors.append("OFFICIAL_WEBSITE_URL must use HTTPS in production")
        if not self.allowed_widget_domains or all(
            domain in {"localhost", "127.0.0.1"} for domain in self.allowed_widget_domains
        ):
            errors.append("ALLOWED_WIDGET_DOMAINS must include a production domain")
        api_host = urlparse(str(self.api_base_url)).hostname
        admin_host = urlparse(str(self.admin_origin)).hostname
        if api_host != admin_host:
            cookie_domain = (self.csrf_cookie_domain or "").lstrip(".")
            if not cookie_domain or not all(
                host and (host == cookie_domain or host.endswith(f".{cookie_domain}"))
                for host in (api_host, admin_host)
            ):
                errors.append(
                    "CSRF_COOKIE_DOMAIN must be a shared parent of API_BASE_URL and ADMIN_ORIGIN"
                )
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.expose_api_docs if self.expose_api_docs is not None else self.environment != "production"

    @property
    def metrics_enabled(self) -> bool:
        return self.expose_metrics if self.expose_metrics is not None else self.environment != "production"

    @property
    def secure_cookies(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Return the exact browser origins permitted to call the API.

        Local browsers commonly use either ``localhost`` or ``127.0.0.1``.
        They are different origins, so accepting the configured loopback origin
        alone breaks the widget when a developer opens the alternate address.
        Keep this convenience strictly local and retain an explicit allowlist
        everywhere else.
        """
        origins = {str(self.widget_origin), str(self.admin_origin), *self.cors_origins_extra}
        if self.environment != "local":
            return sorted(origins)

        for origin in tuple(origins):
            parsed = urlparse(origin)
            if parsed.hostname not in {"localhost", "127.0.0.1"}:
                continue
            alternate_host = "127.0.0.1" if parsed.hostname == "localhost" else "localhost"
            port = f":{parsed.port}" if parsed.port else ""
            origins.add(f"{parsed.scheme}://{alternate_host}{port}")
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    configured_path = os.getenv("CIET_ENV_FILE")
    env_file = Path(configured_path).expanduser() if configured_path else DEFAULT_ENV_FILE
    return Settings(_env_file=env_file if env_file.is_file() else None)
