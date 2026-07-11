from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from jose import jwt
from starlette.datastructures import Headers

from app.core.config import Settings
from app.core.security import create_access_token
from app.models import DocumentChunk
from app.services.pinecone_service import SearchHit, citations_from_hits, keyword_score, rerank_hits
from app.services.upload_security import validate_upload


class EmptyScalarSession:
    async def scalar(self, *_):
        return None


def test_access_token_contains_expected_claims():
    settings = Settings(jwt_secret="change-me-in-production")
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


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret="change-me-in-production")


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
    assert ranked[0].score > 1
    assert citations_from_hits(ranked)[0].section == "Admissions"
    assert keyword_score("admissions scholarships", chunk.content) == 1


@pytest.mark.anyio
async def test_upload_validation_rejects_bad_extension():
    settings = Settings(jwt_secret="change-me-in-production")
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
    settings = Settings(jwt_secret="change-me-in-production")
    file = UploadFile(
        file=BytesIO(b"official notice"),
        filename="notice.txt",
        headers=Headers({"content-type": "text/plain"}),
    )
    checksum = await validate_upload(file, b"official notice", EmptyScalarSession(), settings)
    assert len(checksum) == 64


@pytest.mark.anyio
async def test_bootstrap_disabled_in_production():
    from app.api.routes.auth import bootstrap
    from app.schemas import LoginIn
    from types import SimpleNamespace

    settings = Settings(environment="production", jwt_secret="a-very-long-secret-key-that-is-secure-and-over-20-chars")
    with pytest.raises(HTTPException) as exc:
        await bootstrap(
            LoginIn(username="admin@ciet.edu", password="password123"),
            SimpleNamespace(client=SimpleNamespace(host="test")),
            EmptyScalarSession(),
            settings,
        )
    assert exc.value.status_code == 403
    assert "Bootstrap disabled in production" in exc.value.detail
