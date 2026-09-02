import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.domain_security import is_allowed_origin
from app.services.language import detect_language
from app.services.pinecone_service import PineconeService, PineconeUnavailableError
from app.models import DocumentChunk
from app.services.upload_security import scan_content


def test_domain_allowlist_matches_subdomains():
    assert is_allowed_origin("https://www.ciet.edu/page", ["ciet.edu"])
    assert not is_allowed_origin("https://evil.example", ["ciet.edu"])


def test_language_detection_indic_scripts():
    assert detect_language("అడ్మిషన్ వివరాలు") == "te"
    assert detect_language("प्रवेश जानकारी") == "hi"
    assert detect_language("admission details") == "en"


def test_eicar_upload_scan_is_rejected():
    settings = Settings(jwt_secret="x" * 32)
    try:
        scan_content(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR", settings)
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("EICAR content should be rejected")


def test_missing_pinecone_index_does_not_break_service_construction(monkeypatch):
    import pinecone

    class MissingIndex:
        def __init__(self, **_):
            pass

        def Index(self, _):
            raise RuntimeError("Resource ciet-knowledge not found")

    PineconeService._indexes.clear()
    monkeypatch.setattr(pinecone, "Pinecone", MissingIndex)
    service = PineconeService(Settings(jwt_secret="x" * 32, pinecone_api_key="p" * 24))
    assert service.index is None
    with pytest.raises(PineconeUnavailableError):
        service._initialize_index()
    assert service.index is None
    assert isinstance(service.initialization_error, RuntimeError)


@pytest.mark.anyio
async def test_document_vector_upsert_fails_when_pinecone_is_unavailable():
    service = PineconeService(Settings(jwt_secret="x" * 32))
    chunk = DocumentChunk(
        document_id="00000000-0000-0000-0000-000000000001",
        chunk_index=0,
        content="verified CIET text",
    )
    with pytest.raises(PineconeUnavailableError, match="Pinecone"):
        await service.upsert_chunks([chunk])
