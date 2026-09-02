from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
import jwt
from starlette.datastructures import Headers
from starlette.responses import Response
from app.api.routes.auth import set_auth_cookies

from app.core.config import API_ROOT, PROJECT_ROOT, Settings, discover_project_root
from app.core.security import create_access_token, hash_one_time_token, hash_password, new_one_time_token, validate_password, verify_password
from app.models import Document, DocumentChunk, Metric
from app.services.retrieval import RetrievalService
from app.services.language import detect_language
from app.services.pinecone_service import SearchHit, citations_from_hits, keyword_score, rerank_hits
from app.services.upload_security import validate_upload
from app.services.storage import StorageService
from app.services.website_search import OfficialWebsiteSearch


PRODUCTION_SETTINGS = {
    "environment": "production",
    "jwt_secret": "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_",
    "openai_api_key": "validation-openai-key-fixture-1234567890",
    "allowed_hosts": ["api.example.edu"],
    "api_base_url": "https://api.example.edu",
    "widget_origin": "https://www.example.edu",
    "admin_origin": "https://admin.example.edu",
    "allowed_widget_domains": ["example.edu"],
    "csrf_cookie_domain": "example.edu",
    "clamav_host": "clamav",
    "smtp_host": "smtp.example.edu",
    "smtp_username": "ciet-mailer",
    "smtp_password": "production-smtp-password-value",
    "smtp_from": "no-reply@example.edu",
    "whatsapp_verify_token": "verify-token",
    "whatsapp_app_secret": "production-app-secret-value",
    "whatsapp_access_token": "production-access-token-value",
    "whatsapp_phone_number_id": "phone-id-12345",
}


class EmptyScalarSession:
    async def scalar(self, *_):
        return None


class MetricRows:
    def __init__(self, metrics):
        self.metrics = metrics

    def all(self):
        return list(self.metrics)


class MetricSession:
    def __init__(self):
        self.metrics: list[Metric] = []

    async def scalars(self, *_):
        return MetricRows(self.metrics)


def test_access_token_contains_expected_claims():
    settings = Settings(jwt_secret="x" * 32)
    token = create_access_token("user-1", "content_admin", settings)
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    assert payload["sub"] == "user-1"
    assert payload["role"] == "content_admin"
    assert payload["ver"] == 0


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(environment="production")


def test_production_rejects_documented_secret_placeholders():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            **{
                **PRODUCTION_SETTINGS,
                "jwt_secret": "replace-with-a-64-character-random-secret" + "x" * 30,
            }
        )


def test_production_rejects_short_external_credentials():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(**{**PRODUCTION_SETTINGS, "openai_api_key": "short"})


def test_production_requires_openai_and_hides_operational_endpoints():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(environment="production", jwt_secret="x" * 64)
    settings = Settings(**PRODUCTION_SETTINGS)
    assert not settings.docs_enabled
    assert not settings.metrics_enabled


def test_password_hashing_uses_current_bcrypt_api():
    password_hash = hash_password("a strong admin password")
    assert verify_password("a strong admin password", password_hash)
    assert not verify_password("wrong password", password_hash)
    with pytest.raises(ValueError, match="72"):
        hash_password("é" * 40)


def test_one_time_tokens_are_unpredictable_and_hashed_before_storage():
    token = new_one_time_token()
    assert len(token) >= 64
    assert hash_one_time_token(token) != token
    assert len(hash_one_time_token(token)) == 64
    validate_password("Strong-password-2026")
    with pytest.raises(ValueError, match="12 characters"):
        validate_password("password123")


def test_auth_cookies_are_httponly_samesite_and_secure_in_production():
    response = Response()
    settings = Settings(**PRODUCTION_SETTINGS)
    set_auth_cookies(response, "signed-token", settings)
    cookies = response.headers.getlist("set-cookie")
    access = next(value for value in cookies if value.startswith("ciet_access_token="))
    csrf = next(value for value in cookies if value.startswith("ciet_csrf_token="))
    assert "HttpOnly" in access and "Secure" in access and "SameSite=strict" in access
    assert "HttpOnly" not in csrf and "Secure" in csrf and "SameSite=strict" in csrf
    assert "Domain=" not in access and "Domain=example.edu" in csrf


def test_rate_limits_are_endpoint_specific():
    settings = Settings()
    assert settings.auth_rate_limit == "10/minute"
    assert settings.chat_rate_limit == "30/minute"


def test_configuration_root_discovery_supports_repo_and_flat_container_layouts():
    assert API_ROOT.name == "api"
    assert (PROJECT_ROOT / "package.json").is_file()
    flat_root = Path("/opt/ciet-flat-layout")
    assert discover_project_root(flat_root) == flat_root


def test_direct_platform_environment_accepts_csv_lists(monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.edu,admin.example.edu")
    monkeypatch.setenv("ALLOWED_WIDGET_DOMAINS", '["example.edu", "www.example.edu"]')
    settings = Settings()
    assert settings.allowed_hosts == ["api.example.edu", "admin.example.edu"]
    assert settings.allowed_widget_domains == ["example.edu", "www.example.edu"]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("placements ela unnayi cheppandi", "te"),
        ("bus fee entha undi", "te"),
        ("admissions kaise hain batao", "hi"),
        ("admissions kab start honge", "hi"),
        ("హాస్టల్ ఉందా", "te"),
        ("क्या छात्रावास है", "hi"),
        ("What courses are offered?", "en"),
    ],
)
def test_language_detection_including_romanized_queries(message, expected):
    assert detect_language(message) == expected


def test_rerank_deduplicates_and_boosts_hits():
    chunk = DocumentChunk(
        id=str(uuid4()),
        document_id=str(uuid4()),
        chunk_index=0,
        content="Admissions courses scholarships transport hostel",
        section="Admissions",
    )
    hits = [
        SearchHit(chunk=chunk, score=0.2, source="postgres"),
        SearchHit(chunk=chunk, score=0.3, source="pinecone"),
    ]
    ranked = rerank_hits("admissions scholarships", hits)
    assert len(ranked) == 1
    assert 0 <= ranked[0].score <= 1
    assert citations_from_hits(ranked)[0].section == "Admissions"
    assert keyword_score("admissions scholarships", chunk.content) == 1


class StubSearch:
    def __init__(self, hits):
        self.hits = hits

    async def hybrid_search(self, *_args, **_kwargs):
        return self.hits


@pytest.mark.anyio
async def test_rag_rejects_low_relevance_and_never_assigns_false_confidence():
    chunk = DocumentChunk(id=str(uuid4()), document_id=str(uuid4()), chunk_index=0, content="Unrelated text")
    service = RetrievalService(Settings())
    service.pinecone = StubSearch([SearchHit(chunk=chunk, score=0.2, source="postgres")])
    assert await service._rag(EmptyScalarSession(), "weather tomorrow", "en") is None


@pytest.mark.anyio
async def test_rag_without_ai_fails_closed_without_misleading_citation():
    document = Document(
        id=str(uuid4()), title="CIET Admissions Handbook", source="Registrar", file_path="local://handbook.txt",
        mime_type="text/plain", status="indexed",
    )
    chunk = DocumentChunk(
        id=str(uuid4()), document_id=document.id, chunk_index=0,
        content="CIET admissions applications open in June.", section="Admissions", document=document,
    )
    service = RetrievalService(Settings(openai_api_key=None))
    service.pinecone = StubSearch([SearchHit(chunk=chunk, score=0.8, source="hybrid")])
    result = await service._rag(EmptyScalarSession(), "When do admissions open?", "en")
    assert result is not None
    assert result.route == "fallback" and result.confidence == "low"
    assert result.citations == []
    assert "OPENAI_API_KEY" not in result.answer


@pytest.mark.anyio
async def test_official_website_search_is_bounded_and_same_origin():
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/wp/v2/search":
            return httpx.Response(
                200,
                json=[{"title": "Admissions", "url": "https://ciet.example/admissions/"}],
            )
        if request.url.path == "/admissions/":
            return httpx.Response(
                200,
                text="<html><style>hidden</style><h1>Admissions</h1><p>Apply through the official CIET process.</p></html>",
            )
        return httpx.Response(404)

    settings = Settings(official_website_url="https://ciet.example")
    service = OfficialWebsiteSearch(settings, transport=httpx.MockTransport(handler))
    hits = await service.search("admissions")
    assert len(hits) == 1
    assert hits[0].title == "Admissions"
    assert hits[0].url == "https://ciet.example/admissions/"
    assert hits[0].text == "Admissions Apply through the official CIET process."


@pytest.mark.anyio
async def test_sensitive_metric_queries_never_use_faq_or_website_search():
    service = RetrievalService(Settings(official_website_url="https://ciet.example"))
    assert await service._faq(EmptyScalarSession(), "What is the placement percentage?", "en") is None
    assert await service._website_search("What is the placement percentage?", "en") is None


@pytest.mark.anyio
async def test_placement_metric_create_query_delete_safety_lifecycle():
    service = RetrievalService(Settings())
    session = MetricSession()

    missing, _ = await service.answer(session, "What is the placement percentage?", "en")
    assert missing.route == "metric"
    assert missing.confidence == "low"
    assert "complete verified data" in missing.answer
    assert "0%" not in missing.answer
    assert missing.citations == []

    session.metrics.append(
        Metric(
            name="placement percentage",
            value="92%",
            verified_by="Placement Office",
            source="Official Placement Report",
            is_sensitive_stat=True,
        )
    )
    verified, _ = await service.answer(session, "What is the placement percentage?", "en")
    assert verified.route == "metric"
    assert verified.confidence == "verified"
    assert "92%" in verified.answer
    assert verified.citations[0].title == "Official Placement Report"
    assert verified.citations[0].section == "Verified by Placement Office"

    for query, language in [
        ("ప్లేస్‌మెంట్ శాతం ఎంత?", "te"),
        ("प्लेसमेंट प्रतिशत क्या है?", "hi"),
        ("placement percentage entha undi", "te"),
        ("placement percentage kitna hai", "hi"),
    ]:
        localized, _ = await service.answer(session, query, language)
        assert localized.confidence == "verified"
        assert "92%" in localized.answer

    session.metrics.clear()
    deleted, _ = await service.answer(session, "What is the placement percentage?", "en")
    assert deleted.confidence == "low"
    assert "complete verified data" in deleted.answer
    assert "0%" not in deleted.answer


@pytest.mark.anyio
async def test_worker_disposes_async_pool_before_task_event_loop_closes(monkeypatch):
    from app.workers import tasks

    calls: list[str] = []

    async def process(document_id: str):
        calls.append(f"process:{document_id}")

    async def dispose():
        calls.append("dispose")

    monkeypatch.setattr(tasks, "_process_document", process)
    monkeypatch.setattr(tasks, "engine", SimpleNamespace(dispose=dispose))
    await tasks._run_document_task("document-1")
    assert calls == ["process:document-1", "dispose"]


@pytest.mark.anyio
async def test_upload_validation_rejects_bad_extension():
    settings = Settings(jwt_secret="x" * 32)
    file = UploadFile(
        file=BytesIO(b"not actually malware"),
        filename="malware.exe",
        headers=Headers({"content-type": "application/octet-stream"}),
    )
    with pytest.raises(HTTPException) as exc:
        await validate_upload(file, b"not actually malware", EmptyScalarSession(), settings)
    assert exc.value.status_code == 415


@pytest.mark.anyio
async def test_upload_validation_accepts_text_file():
    settings = Settings(jwt_secret="x" * 32)
    file = UploadFile(
        file=BytesIO(b"official notice"),
        filename="notice.txt",
        headers=Headers({"content-type": "text/plain"}),
    )
    checksum = await validate_upload(file, b"official notice", EmptyScalarSession(), settings)
    assert len(checksum) == 64


@pytest.mark.anyio
async def test_local_storage_persists_reads_and_deletes(tmp_path):
    storage = StorageService(Settings(local_storage_path=str(tmp_path)))
    path = await storage.put("documents/notice.txt", b"official notice", "text/plain")
    assert path == "local://notice.txt"
    assert await storage.get(path) == b"official notice"
    await storage.delete(path)
    assert not (tmp_path / "notice.txt").exists()


@pytest.mark.anyio
async def test_bootstrap_disabled_in_production():
    from app.api.routes.auth import bootstrap
    from app.schemas import LoginIn
    from types import SimpleNamespace

    settings = Settings(**PRODUCTION_SETTINGS)
    with pytest.raises(HTTPException) as exc:
        await bootstrap.__wrapped__(
            LoginIn(username="admin@ciet.edu", password="password123"),
            SimpleNamespace(client=SimpleNamespace(host="test")),
            Response(),
            EmptyScalarSession(),
            settings,
        )
    assert exc.value.status_code == 403
    assert "only available in local development" in exc.value.detail


@pytest.mark.anyio
async def test_bootstrap_disabled_in_staging():
    from app.api.routes.auth import bootstrap
    from app.schemas import LoginIn
    from types import SimpleNamespace

    with pytest.raises(HTTPException) as exc:
        await bootstrap.__wrapped__(
            LoginIn(username="admin@ciet.edu", password="password123"),
            SimpleNamespace(client=SimpleNamespace(host="test")),
            Response(),
            EmptyScalarSession(),
            Settings(environment="staging", jwt_secret="x" * 64),
        )
    assert exc.value.status_code == 403
