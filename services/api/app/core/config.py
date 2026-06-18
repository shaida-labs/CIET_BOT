from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CIET AI Assistant API"
    environment: Literal["local", "staging", "production"] = "local"
    api_base_url: AnyHttpUrl | str = "http://localhost:8000"
    widget_origin: str = "http://localhost:5173"
    admin_origin: str = "http://localhost:5174"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_widget_domains: list[str] = [
        "localhost",
        "127.0.0.1",
    ]

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ciet_ai"
    jwt_secret: str = Field(default="change-me-in-production", min_length=20)
    jwt_issuer: str = "ciet-ai"
    jwt_audience: str = "ciet-admin"
    access_token_minutes: int = 30

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    openai_mini_model: str = "gpt-5.5-mini"
    embedding_model: str = "text-embedding-3-large"

    pinecone_api_key: str | None = None
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_index: str = "ciet-knowledge"
    pinecone_namespace: str = "ciet"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    max_upload_bytes: int = 25 * 1024 * 1024
    clamav_host: str | None = None
    clamav_port: int = 3310

    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "ciet-ai-documents"

    whatsapp_verify_token: str = "change-me"
    whatsapp_app_secret: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None

    sentry_dsn: str | None = None
    rate_limit: str = "80/minute"

    safe_fallback: str = (
        "I could not find verified CIET information for this question. "
        "Rather than guess, please contact the CIET help desk for an official answer."
    )

    @field_validator("allowed_hosts", "allowed_widget_domains", mode="before")
    @classmethod
    def parse_csv_lists(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment == "production" and self.jwt_secret == "change-me-in-production":
            raise ValueError("JWT_SECRET must be changed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
