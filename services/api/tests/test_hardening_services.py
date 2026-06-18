from fastapi import HTTPException

from app.core.config import Settings
from app.core.domain_security import is_allowed_origin
from app.services.language import detect_language
from app.services.upload_security import scan_content


def test_domain_allowlist_matches_subdomains():
    assert is_allowed_origin("https://www.ciet.edu/page", ["ciet.edu"])
    assert not is_allowed_origin("https://evil.example", ["ciet.edu"])


def test_language_detection_indic_scripts():
    assert detect_language("అడ్మిషన్ వివరాలు") == "te"
    assert detect_language("प्रवेश जानकारी") == "hi"
    assert detect_language("admission details") == "en"


def test_eicar_upload_scan_is_rejected():
    settings = Settings(jwt_secret="change-me-in-production")
    try:
        scan_content(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR", settings)
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("EICAR content should be rejected")
