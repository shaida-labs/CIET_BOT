from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes.chat import chat
from app.api.routes.health import healthz
from app.api.routes.whatsapp import verify_webhook
from app.core.config import Settings
from app.core.domain_security import is_allowed_origin
from app.models import Conversation, ConversationMessage
from app.schemas import ChatRequest


class EmptyScalarResult:
    def all(self):
        return []


class FakeSession:
    def __init__(self):
        self.objects = []

    async def get(self, *_):
        return None

    async def scalars(self, *_):
        return EmptyScalarResult()

    async def scalar(self, *_):
        return None

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid4())
        if isinstance(obj, Conversation) and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        if isinstance(obj, ConversationMessage) and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        self.objects.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, _):
        return None


@pytest.mark.anyio
async def test_healthz():
    assert await healthz() == {"status": "ok"}


def test_local_widget_origin_is_allowed():
    settings = Settings(jwt_secret="change-me-in-production")
    assert settings.widget_origin == "http://localhost:5173"
    assert is_allowed_origin(settings.widget_origin, settings.allowed_widget_domains)


@pytest.mark.anyio
async def test_chat_safe_fallback_contract():
    response = await chat(
        ChatRequest(message="What is the exact bus fee?", language="en", channel="website"),
        SimpleNamespace(client=SimpleNamespace(host="test-client")),
        FakeSession(),
        Settings(jwt_secret="change-me-in-production"),
    )
    assert response.route in {"metric", "fallback"}
    assert response.message.confidence in {"medium", "low"}


@pytest.mark.anyio
async def test_whatsapp_webhook_verification():
    response = await verify_webhook(
        hub_mode="subscribe",
        hub_challenge="abc123",
        hub_verify_token="change-me",
        settings=Settings(jwt_secret="change-me-in-production"),
    )
    assert response == "abc123"
