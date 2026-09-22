"""Client-supplied identifiers must fail validation before touching the database.

Every identifier below is bound to a PostgreSQL UUID column.  A value that only
satisfies a length check reaches asyncpg, which raises a DataError from inside
the request handler and surfaces as an unhandled 500 instead of a 422.
"""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.security import Role, current_user
from app.db.session import get_session
from app.main import app
from app.models import AdminUser

WIDGET_ORIGIN = {"Origin": "http://localhost:5173"}
ADMIN_ORIGIN = {"Origin": "http://localhost:5174"}

# Too short for the old length check, and long enough to pass it while still
# not being a UUID.
SHORT_ID = "smoke-test-1"
LENGTH_CONFORMING_BUT_INVALID = "z" * 36

ADMIN_FAQ_PATH = "/api/v1/admin/faqs/"


class EmptyScalarResult:
    def unique(self):
        return self

    def all(self):
        return []


class FakeSession:
    """Stand in for the database so these tests never open a connection."""

    def __init__(self):
        self.objects = []

    async def get(self, *_args, **_kwargs):
        return None

    async def scalars(self, *_args, **_kwargs):
        return EmptyScalarResult()

    async def scalar(self, *_args, **_kwargs):
        return None

    def add(self, obj):
        # Column defaults only run on INSERT, so a fake flush must supply them.
        if hasattr(obj, "id") and obj.id is None:
            obj.id = str(uuid4())
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        self.objects.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


@pytest.fixture(autouse=True)
def fake_session():
    session = FakeSession()
    app.dependency_overrides[get_session] = lambda: session
    yield session
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def signed_in_super_admin():
    """Grant admin permissions without a real login or an admin row."""
    admin = AdminUser(id=str(uuid4()), email="tester@example.edu", role=Role.super_admin, is_active=True)
    app.dependency_overrides[current_user] = lambda: admin
    yield admin
    app.dependency_overrides.pop(current_user, None)


@pytest.fixture(autouse=True)
def settings_without_external_services():
    """Keep retrieval away from the response cache, OpenAI, and Pinecone."""
    settings = Settings(response_cache_seconds=0, openai_api_key=None, pinecone_api_key=None)
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


def client_for(ip: str) -> httpx.AsyncClient:
    """Isolate each test in its own in-memory rate-limit bucket."""
    transport = httpx.ASGITransport(app=app, client=(ip, 41000))
    return httpx.AsyncClient(transport=transport, base_url="http://localhost")


def error_loc(response: httpx.Response) -> list[str]:
    """Read the location of the first rejection from the validation handler."""
    body = response.json()
    assert body["detail"] == "Invalid request"
    return list(body["errors"][0]["loc"])


@pytest.mark.anyio
async def test_short_conversation_id_is_rejected_as_422():
    async with client_for("198.51.100.10") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": SHORT_ID},
            headers=WIDGET_ORIGIN,
        )
    assert response.status_code == 422
    assert error_loc(response) == ["body", "conversation_id"]


@pytest.mark.anyio
async def test_length_conforming_conversation_id_is_still_rejected():
    """A 36-character non-UUID previously passed validation and crashed asyncpg."""
    async with client_for("198.51.100.11") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": LENGTH_CONFORMING_BUT_INVALID},
            headers=WIDGET_ORIGIN,
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_valid_conversation_id_is_accepted():
    """The new constraint must not reject well-formed identifiers."""
    async with client_for("198.51.100.12") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "conversation_id": str(uuid4())},
            headers=WIDGET_ORIGIN,
        )
    assert response.status_code == 200
    assert response.json()["conversation_id"]


@pytest.mark.anyio
async def test_omitted_conversation_id_still_starts_a_conversation():
    async with client_for("198.51.100.13") as client:
        response = await client.post("/api/v1/chat", json={"message": "Hello"}, headers=WIDGET_ORIGIN)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_malformed_feedback_message_id_is_rejected():
    async with client_for("198.51.100.14") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={"message_id": LENGTH_CONFORMING_BUT_INVALID, "rating": "up"},
            headers=WIDGET_ORIGIN,
        )
    assert response.status_code == 422
    assert error_loc(response) == ["body", "message_id"]


@pytest.mark.anyio
async def test_malformed_handoff_conversation_id_is_rejected():
    async with client_for("198.51.100.15") as client:
        response = await client.post(
            "/api/v1/support/tickets",
            json={
                "conversation_id": LENGTH_CONFORMING_BUT_INVALID,
                "contact": "student@example.edu",
                "contact_consent": True,
            },
            headers=WIDGET_ORIGIN,
        )
    assert response.status_code == 422
    assert error_loc(response) == ["body", "conversation_id"]


@pytest.mark.anyio
async def test_malformed_admin_path_id_is_rejected_for_signed_in_callers():
    """Auth runs first, so this only surfaces the 422 once a caller is signed in."""
    async with client_for("198.51.100.16") as client:
        response = await client.delete(ADMIN_FAQ_PATH + LENGTH_CONFORMING_BUT_INVALID, headers=ADMIN_ORIGIN)
    assert response.status_code == 422
    assert error_loc(response) == ["path", "faq_id"]


@pytest.mark.anyio
async def test_valid_admin_path_id_reaches_the_handler():
    """A well-formed id passes validation and falls through to a clean 404."""
    async with client_for("198.51.100.17") as client:
        response = await client.delete(ADMIN_FAQ_PATH + str(uuid4()), headers=ADMIN_ORIGIN)
    assert response.status_code == 404
    assert response.json()["status_code"] == 404
    assert response.json()["detail"] == "FAQ not found"
