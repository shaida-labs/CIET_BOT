"""Language-switch translation must reword only, stay fail-closed, and be origin-guarded.

The widget asks this endpoint to re-render history a visitor already received.
It must never invent an answer, never claim a translation that did not land in
the target script, and never accept a request from a foreign browser origin.
"""

from typing import ClassVar

import httpx
import pytest

from app.api.routes import chat as chat_routes
from app.core.config import Settings
from app.main import app
from app.services.language import (
    needs_translation,
    strip_translation_delimiters,
    translation_accepted,
)
from app.services.llm import LLMUnavailableError

WIDGET_ORIGIN = {"Origin": "http://localhost:5173"}

TRANSLATED = {
    "te": "ఇది తెలుగు అనువాదం.",
    "hi": "यह हिन्दी अनुवाद है।",
    "en": "This is an English translation.",
}


def test_needs_translation_only_for_lines_missing_the_target():
    assert needs_translation("Where is CIET located?", "te")
    assert needs_translation("CIET ఎక్కడ ఉంది?", "en")
    assert needs_translation("CIET कहाँ स्थित है?", "te")
    assert not needs_translation("CIET ఎక్కడ ఉంది?", "te")
    assert not needs_translation("plain English words", "en")
    assert not needs_translation("08:20", "te")
    assert not needs_translation("8", "en")


def test_translation_accepted_requires_the_target_script():
    assert translation_accepted("Hello", TRANSLATED["te"], "te")
    assert not translation_accepted("Hello", "Hello", "te")
    assert translation_accepted("నమస్తే", TRANSLATED["en"], "en")
    assert not translation_accepted("నమస్తే", "నమస్తే", "en")
    assert not translation_accepted("Hello", "   ", "te")
    # Script-neutral input passes through without claiming a translation.
    assert translation_accepted("8", "8", "te")


def test_translation_accepted_rejects_echoed_prompt_delimiters():
    """The prompt's <text> wrapper must never survive verification."""
    assert not translation_accepted("Hello", "<text>హలో</text>", "te")
    assert not translation_accepted("Hello", "</text>", "te")


def test_strip_translation_delimiters_removes_only_the_wrapper():
    assert strip_translation_delimiters("<text>\nహలో ప్రపంచం\n</text>") == "హలో ప్రపంచం"
    assert strip_translation_delimiters("<text>హలో</text>") == "హలో"
    assert strip_translation_delimiters("</text>") == ""
    assert strip_translation_delimiters("TEXT:\nTARGET_LANGUAGE: Telugu") == ""
    # Regular translated output passes through untouched.
    assert strip_translation_delimiters(TRANSLATED["te"]) == TRANSLATED["te"]


class _WorkingLLM:
    """Stub provider whose output genuinely lands in the requested script."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        return TRANSLATED[language]


class _NoProviderLLM:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        raise LLMUnavailableError("not_configured", "AI translation is unavailable")


class _WrongScriptLLM:
    """Stub that always answers in the wrong language to force fail-closed."""

    calls: ClassVar[list[str]] = []

    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        _WrongScriptLLM.calls.append(language)
        return TRANSLATED["en"] if language != "en" else TRANSLATED["te"]


class _MustNotBeCalledLLM:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        raise AssertionError("model was called for text already in the target language")


def _client():
    transport = httpx.ASGITransport(app=app, client=("198.51.100.60", 4321))
    return httpx.AsyncClient(transport=transport, base_url="http://localhost")


@pytest.mark.anyio
async def test_translate_endpoint_renders_history_in_the_target_language(monkeypatch):
    monkeypatch.setattr(chat_routes, "LLMService", _WorkingLLM)
    payload = {
        "language": "te",
        "messages": [
            {"id": "welcome", "role": "assistant", "content": "Hello, how can I help?"},
            {"id": "m1", "role": "user", "content": "Where is CIET located?"},
        ],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "te"
    assert body["translated"] is True
    # Identifiers echo back so the widget can apply results without index races.
    assert [item["id"] for item in body["messages"]] == ["welcome", "m1"]
    assert body["messages"][0]["content"] == TRANSLATED["te"]
    assert body["messages"][0]["translated"] is True


@pytest.mark.anyio
async def test_translate_endpoint_keeps_originals_when_no_provider_works(monkeypatch):
    monkeypatch.setattr(chat_routes, "LLMService", _NoProviderLLM)
    payload = {
        "language": "hi",
        "messages": [{"id": "m1", "role": "user", "content": "Where is CIET located?"}],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is False
    assert body["messages"][0]["content"] == "Where is CIET located?"
    assert body["messages"][0]["translated"] is False


@pytest.mark.anyio
async def test_translate_endpoint_rejects_output_that_never_changed_language(monkeypatch):
    """Zero false pass: a wrong-script reply is retried once, then discarded."""
    _WrongScriptLLM.calls = []
    monkeypatch.setattr(chat_routes, "LLMService", _WrongScriptLLM)
    payload = {
        "language": "te",
        "messages": [{"id": "m1", "role": "assistant", "content": "Admissions close in July."}],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is False
    assert body["messages"][0]["content"] == "Admissions close in July."
    assert _WrongScriptLLM.calls == ["te", "te"]


@pytest.mark.anyio
async def test_translate_endpoint_skips_lines_already_in_the_target_language(monkeypatch):
    monkeypatch.setattr(chat_routes, "LLMService", _MustNotBeCalledLLM)
    payload = {
        "language": "te",
        "messages": [
            {"id": "m1", "role": "user", "content": "CIET ఎక్కడ ఉంది?"},
            {"id": "m2", "role": "assistant", "content": "08:20"},
        ],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is False
    assert [item["content"] for item in body["messages"]] == ["CIET ఎక్కడ ఉంది?", "08:20"]


class _EchoingWrapperLLM:
    """Model that copies the prompt's structural <text> wrapper into replies."""

    calls: ClassVar[list[str]] = []

    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        _EchoingWrapperLLM.calls.append(language)
        return f"<text>\n{TRANSLATED[language]}\n</text>"


class _RateLimitedThenWorkingLLM:
    """Chain that dies on a quota window, then recovers on the next pass."""

    calls: ClassVar[int] = 0

    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, language: str) -> str:
        _RateLimitedThenWorkingLLM.calls += 1
        if _RateLimitedThenWorkingLLM.calls == 1:
            raise LLMUnavailableError("rate_limit", "AI translation is temporarily unavailable")
        return TRANSLATED[language]


async def _fail_if_waited(seconds: float) -> None:
    raise AssertionError(f"must not wait here (waited {seconds}s)")


@pytest.mark.anyio
async def test_translate_endpoint_waits_out_a_rate_limit_and_completes_the_switch(monkeypatch):
    """A back-to-back switch exhausts minute quotas: one bounded wait recovers it.

    The widget never re-asks for a failed switch, so without this the history
    would stay half-translated forever.
    """
    _RateLimitedThenWorkingLLM.calls = 0
    waits: list[float] = []

    async def _record_wait(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(chat_routes, "sleep", _record_wait)
    monkeypatch.setattr(chat_routes, "LLMService", _RateLimitedThenWorkingLLM)
    payload = {
        "language": "hi",
        "messages": [
            {"id": "m1", "role": "user", "content": "Which time does the bus reach Narakoduru?"},
        ],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is True
    assert body["messages"][0]["content"] == TRANSLATED["hi"]
    assert body["messages"][0]["translated"] is True
    # Exactly one recovery wait, landing inside the next quota minute (1-61s).
    assert len(waits) == 1
    assert 1 <= waits[0] <= 61


@pytest.mark.anyio
async def test_translate_endpoint_skips_the_wait_when_the_first_pass_lands(monkeypatch):
    monkeypatch.setattr(chat_routes, "sleep", _fail_if_waited)
    monkeypatch.setattr(chat_routes, "LLMService", _WorkingLLM)
    payload = {
        "language": "te",
        "messages": [{"id": "m1", "role": "user", "content": "Where is CIET located?"}],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    assert response.json()["translated"] is True


@pytest.mark.anyio
async def test_translate_endpoint_fails_fast_without_waiting_when_unconfigured(monkeypatch):
    """A recovery wait only helps quota windows; a dead chain stays fail-fast."""
    monkeypatch.setattr(chat_routes, "sleep", _fail_if_waited)
    monkeypatch.setattr(chat_routes, "LLMService", _NoProviderLLM)
    payload = {
        "language": "hi",
        "messages": [{"id": "m1", "role": "user", "content": "Where is CIET located?"}],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is False
    assert body["messages"][0]["content"] == "Where is CIET located?"


@pytest.mark.anyio
async def test_translate_endpoint_strips_wrapper_markup_the_model_echoes(monkeypatch):
    """The chat must never show the prompt's <text> delimiters on screen."""
    _EchoingWrapperLLM.calls = []
    monkeypatch.setattr(chat_routes, "LLMService", _EchoingWrapperLLM)
    payload = {
        "language": "te",
        "messages": [{"id": "m1", "role": "user", "content": "Where is CIET located?"}],
    }
    async with _client() as client:
        response = await client.post("/api/v1/chat/translate", json=payload, headers=WIDGET_ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["translated"] is True
    assert body["messages"][0]["content"] == TRANSLATED["te"]
    assert "<text>" not in body["messages"][0]["content"]
    assert "</text>" not in body["messages"][0]["content"]


@pytest.mark.anyio
async def test_translate_endpoint_rejects_disallowed_origin():
    payload = {
        "language": "en",
        "messages": [{"id": "m1", "role": "user", "content": "నమస్తే"}],
    }
    async with _client() as client:
        response = await client.post(
            "/api/v1/chat/translate",
            json=payload,
            headers={"Origin": "https://evil.example"},
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Unauthorized widget domain"}


@pytest.mark.anyio
async def test_translate_request_bounds_are_validated():
    too_many = {
        "language": "te",
        "messages": [
            {"id": f"m{index}", "role": "user", "content": "Hello"}
            for index in range(41)
        ],
    }
    too_long = {
        "language": "te",
        "messages": [{"id": "m1", "role": "user", "content": "x" * 3001}],
    }
    missing_id = {"language": "te", "messages": [{"role": "user", "content": "Hello"}]}
    async with _client() as client:
        for body in (too_many, too_long, missing_id):
            response = await client.post("/api/v1/chat/translate", json=body, headers=WIDGET_ORIGIN)
            assert response.status_code == 422
