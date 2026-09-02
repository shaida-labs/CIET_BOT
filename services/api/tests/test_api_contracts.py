from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from starlette.responses import Response

from app.api.routes.chat import (
    WIDGET_VISITOR_COOKIE,
    chat,
    create_handoff_ticket,
    recent_conversation_memory,
)
from app.api.routes.health import healthz
from app.api.routes.whatsapp import inbound_claim_statement, verify_webhook, webhook_values
from app.core.config import Settings
from app.core.domain_security import is_allowed_origin
from app.models import Conversation, ConversationMessage
from app.schemas import ChatRequest, HandoffTicketIn
from app.services.retrieval import contextual_query


class EmptyScalarResult:
    def all(self):
        return []


class ScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


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


class OwnedConversationSession(FakeSession):
    def __init__(self, conversation):
        super().__init__()
        self.conversation = conversation

    async def get(self, *_):
        return self.conversation


class ConversationMemorySession(OwnedConversationSession):
    def __init__(self, conversation, messages):
        super().__init__(conversation)
        self.messages = messages

    async def scalars(self, *_):
        # The production query is descending; preserve that order in this fake.
        return ScalarResult(self.messages)


@pytest.mark.anyio
async def test_healthz():
    assert await healthz() == {"status": "ok"}


def test_local_widget_origin_is_allowed():
    settings = Settings(jwt_secret="x" * 32)
    assert settings.widget_origin == "http://localhost:5173"
    assert is_allowed_origin(settings.widget_origin, settings.allowed_widget_domains)
    assert settings.cors_origins == [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
    ]
    assert is_allowed_origin("https://help.ciet.edu", ["ciet.edu"])
    assert not is_allowed_origin("https://evilciet.edu", ["ciet.edu"])


def test_local_cors_supports_docker_and_vite_frontend_modes():
    settings = Settings(
        jwt_secret="x" * 32,
        widget_origin="http://localhost:8080",
        admin_origin="http://localhost:8080",
        cors_origins_extra="http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174",
    )
    assert settings.cors_origins == [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
    ]


def test_contextual_query_uses_only_a_short_follow_up_and_the_latest_user_topic():
    memory = [
        ("user", "Tell me about admissions"),
        ("assistant", "Admissions information is available."),
    ]
    assert contextual_query("What about fees?", memory) == "Tell me about admissions"
    assert contextual_query("Where is CIET located?", memory) == "Where is CIET located?"


@pytest.mark.anyio
async def test_conversation_memory_is_loaded_from_server_records_in_bounded_order():
    conversation = Conversation(id=str(uuid4()), channel="website", user_ref="visitor")
    newest = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="The answer to your admissions question.",
    )
    oldest = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content="Tell me about admissions",
    )
    session = ConversationMemorySession(conversation, [newest, oldest])
    memory = await recent_conversation_memory(
        session,
        conversation.id,
        Settings(jwt_secret="x" * 32, conversation_memory_messages=2, conversation_memory_characters=100),
    )
    assert memory == [
        ("user", "Tell me about admissions"),
        ("assistant", "The answer to your admissions question."),
    ]


def test_whatsapp_inbound_claim_is_idempotent():
    statement = str(inbound_claim_statement("message-1", "15551234567", "text")).upper()
    assert "ON CONFLICT (PROVIDER_MESSAGE_ID) DO NOTHING" in statement


def test_whatsapp_payload_validation_handles_malformed_envelopes():
    with pytest.raises(Exception) as exc:
        webhook_values([])
    assert exc.value.status_code == 422
    assert webhook_values({"entry": [None, {"changes": "invalid"}]}) == []


@pytest.mark.anyio
async def test_chat_safe_fallback_contract():
    response = await chat.__wrapped__(
        ChatRequest(message="What is the exact bus fee?", language="en", channel="website"),
        SimpleNamespace(client=SimpleNamespace(host="test-client")),
        Response(),
        FakeSession(),
        Settings(jwt_secret="x" * 32),
    )
    assert response.route in {"metric", "fallback"}
    assert response.message.confidence in {"medium", "low"}
    assert response.message.language == "en"


@pytest.mark.anyio
async def test_chat_rejects_conversation_from_another_client():
    conversation = Conversation(
        id=str(uuid4()),
        channel="website",
        user_ref="original-client",
    )
    with pytest.raises(Exception) as exc:
        await chat.__wrapped__(
            ChatRequest(
                message="What are the admissions details?",
                channel="website",
                conversation_id=conversation.id,
                user_ref="different-client",
            ),
            SimpleNamespace(client=SimpleNamespace(host="different-host")),
            Response(),
            OwnedConversationSession(conversation),
            Settings(jwt_secret="x" * 32),
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_website_conversation_ownership_uses_httponly_visitor_cookie():
    owner = "visitor-owner-value-that-is-long-enough-123456"
    conversation = Conversation(id=str(uuid4()), channel="website", user_ref=owner)
    response = Response()
    result = await chat.__wrapped__(
        ChatRequest(
            message="What is the exact bus fee?",
            channel="website",
            conversation_id=conversation.id,
            user_ref="attacker-controlled-value",
        ),
        SimpleNamespace(cookies={WIDGET_VISITOR_COOKIE: owner}),
        response,
        OwnedConversationSession(conversation),
        Settings(jwt_secret="x" * 32),
    )
    assert result.conversation_id == conversation.id
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
async def test_handoff_ticket_requires_consent_and_the_owned_conversation():
    owner = "visitor-owner-value-that-is-long-enough-123456"
    conversation = Conversation(id=str(uuid4()), channel="website", user_ref=owner)
    session = OwnedConversationSession(conversation)
    ticket = await create_handoff_ticket.__wrapped__(
        HandoffTicketIn(
            conversation_id=conversation.id,
            contact="student@example.edu",
            contact_consent=True,
        ),
        SimpleNamespace(cookies={WIDGET_VISITOR_COOKIE: owner}),
        session,
    )
    assert ticket.conversation_id == conversation.id
    assert ticket.contact == "student@example.edu"
    assert ticket.contact_consent is True

    with pytest.raises(Exception) as exc:
        await create_handoff_ticket.__wrapped__(
            HandoffTicketIn(
                conversation_id=conversation.id,
                contact="student@example.edu",
                contact_consent=True,
            ),
            SimpleNamespace(cookies={WIDGET_VISITOR_COOKIE: "another-visitor-owner-value-that-is-long-enough"}),
            session,
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_first_widget_request_issues_an_httponly_owner_cookie():
    response = Response()
    await chat.__wrapped__(
        ChatRequest(message="What is the exact bus fee?", channel="website"),
        SimpleNamespace(cookies={}),
        response,
        FakeSession(),
        Settings(jwt_secret="x" * 32),
    )
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{WIDGET_VISITOR_COOKIE}=")
    assert "HttpOnly" in cookie


@pytest.mark.anyio
async def test_public_chat_endpoint_rejects_non_website_channels():
    with pytest.raises(Exception) as exc:
        await chat.__wrapped__(
            ChatRequest(message="hello", channel="whatsapp", user_ref="spoofed"),
            SimpleNamespace(cookies={}),
            Response(),
            FakeSession(),
            Settings(jwt_secret="x" * 32),
        )
    assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_whatsapp_webhook_verification():
    response = await verify_webhook(
        hub_mode="subscribe",
        hub_challenge="abc123",
        hub_verify_token="change-me",
        settings=Settings(jwt_secret="x" * 32),
    )
    assert response == "abc123"
