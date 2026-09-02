from io import BytesIO
import json
from tempfile import SpooledTemporaryFile

import jwt
import pytest
from fastapi import HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import Headers
from starlette.responses import Response

from app.api.routes.auth import logout
from app.api.routes.whatsapp import verify_signature
from app.core.config import Settings
from app.core.domain_security import is_allowed_origin
from app.core.request_limits import body_limit_for
from app.core.security import Role, create_access_token, current_user, require_roles
from app.main import validation_exception_handler
from app.models import AdminUser, AuditLog
from app.schemas import LoginIn
from app.services.audit import sanitize_audit_metadata
from app.services.storage import StorageService
from app.services.upload_security import read_upload_limited, validate_upload


class EmptyScalarSession:
    async def scalar(self, *_):
        return None


class UserSession:
    def __init__(self, user):
        self.user = user
        self.added = []
        self.commits = 0

    async def scalar(self, *_):
        return self.user

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


@pytest.mark.anyio
async def test_upload_read_stops_at_configured_limit():
    file_object = SpooledTemporaryFile()
    file_object.write(b"123456")
    file_object.seek(0)
    upload = UploadFile(file=file_object, filename="notice.txt")
    with pytest.raises(HTTPException) as exc:
        await read_upload_limited(upload, 5)
    assert exc.value.status_code == 413


@pytest.mark.anyio
async def test_upload_rejects_spoofed_pdf_and_path_filename():
    settings = Settings()
    spoofed = UploadFile(
        file=BytesIO(b"plain text"),
        filename="notice.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    with pytest.raises(HTTPException) as exc:
        await validate_upload(spoofed, b"plain text", EmptyScalarSession(), settings)
    assert exc.value.status_code == 415

    traversing = UploadFile(
        file=BytesIO(b"safe text"),
        filename="../notice.txt",
        headers=Headers({"content-type": "text/plain"}),
    )
    with pytest.raises(HTTPException) as exc:
        await validate_upload(traversing, b"safe text", EmptyScalarSession(), settings)
    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_local_storage_rejects_traversal(tmp_path):
    storage = StorageService(Settings(local_storage_path=str(tmp_path)))
    with pytest.raises(ValueError, match="Invalid local storage path"):
        await storage.get("local://../../etc/passwd")


def test_unconfigured_whatsapp_webhook_fails_closed():
    with pytest.raises(HTTPException) as exc:
        verify_signature(b"{}", None, Settings())
    assert exc.value.status_code == 503


def test_origin_validation_rejects_non_http_and_userinfo_urls():
    assert not is_allowed_origin("javascript://ciet.edu", ["ciet.edu"])
    assert not is_allowed_origin("https://attacker@ciet.edu", ["ciet.edu"])


def test_request_body_limits_are_route_specific():
    settings = Settings(max_upload_bytes=10_000, multipart_overhead_bytes=65_536)
    assert body_limit_for("/api/v1/chat", "POST", settings) == settings.max_json_body_bytes
    assert body_limit_for("/api/v1/whatsapp/webhook", "POST", settings) == 1024 * 1024
    assert body_limit_for("/api/v1/admin/documents", "POST", settings) == 75_536
    assert body_limit_for("/healthz", "GET", settings) is None


def test_audit_metadata_redacts_secret_fields_recursively():
    sanitized = sanitize_audit_metadata(
        {"filename": "notice.pdf", "access_token": "jwt", "nested": {"password": "secret"}}
    )
    assert sanitized == {
        "filename": "notice.pdf",
        "access_token": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }


def test_session_version_is_cryptographically_bound_to_token():
    settings = Settings(jwt_secret="x" * 32)
    token = create_access_token(
        "user-1",
        "content_admin",
        settings,
        session_version=7,
    )
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    assert claims["ver"] == 7


@pytest.mark.anyio
async def test_revoked_session_version_rejects_pre_logout_token():
    settings = Settings(jwt_secret="x" * 32)
    user = AdminUser(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@ciet.edu",
        password_hash="unused",
        role="content_admin",
        is_active=True,
        session_version=2,
    )
    stale_token = create_access_token(user.id, user.role, settings, session_version=1)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    with pytest.raises(HTTPException) as exc:
        await current_user(request, stale_token, UserSession(user), settings)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_logout_revokes_sessions_and_writes_an_audit_record():
    settings = Settings(jwt_secret="x" * 32)
    user = AdminUser(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@ciet.edu",
        password_hash="unused",
        role="content_admin",
        is_active=True,
        session_version=2,
    )
    session = UserSession(user)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [],
            "client": ("198.51.100.5", 1234),
        }
    )
    response = Response()
    await logout(request, response, user, session, settings)
    assert user.session_version == 3
    assert session.commits == 1
    assert any(isinstance(item, AuditLog) and item.action == "logout" for item in session.added)


@pytest.mark.anyio
async def test_admissions_and_placement_admin_permissions_are_separated():
    faq_guard = require_roles(Role.content_admin, Role.admissions_admin)
    metric_guard = require_roles(Role.placement_admin)
    document_guard = require_roles(Role.content_admin)
    super_guard = require_roles(Role.super_admin)

    admissions = AdminUser(role=Role.admissions_admin)
    placement = AdminUser(role=Role.placement_admin)
    content = AdminUser(role=Role.content_admin)
    viewer = AdminUser(role=Role.viewer)
    super_user = AdminUser(role=Role.super_admin)
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/admin/faqs", "headers": []})

    assert await faq_guard(request, admissions) is admissions
    assert await faq_guard(request, content) is content
    assert await metric_guard(request, placement) is placement
    assert await document_guard(request, content) is content
    assert await faq_guard(request, viewer) is viewer
    with pytest.raises(HTTPException) as viewer_error:
        await super_guard(request, viewer)
    assert viewer_error.value.status_code == 403
    for guard in (faq_guard, metric_guard, document_guard, super_guard):
        assert await guard(request, super_user) is super_user

    for guard, user in (
        (metric_guard, admissions),
        (document_guard, admissions),
        (faq_guard, placement),
        (document_guard, placement),
        (metric_guard, content),
        (super_guard, admissions),
        (super_guard, placement),
        (super_guard, content),
    ):
        with pytest.raises(HTTPException) as exc:
            await guard(request, user)
        assert exc.value.status_code == 403


@pytest.mark.anyio
async def test_validation_error_never_echoes_submitted_password():
    password = "do-not-echo-this-password" * 4
    with pytest.raises(ValidationError) as validation:
        LoginIn(username="admin@ciet.edu", password=password)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/auth/login", "headers": []})
    response = await validation_exception_handler(
        request,
        RequestValidationError(validation.value.errors()),
    )
    payload = json.loads(response.body)
    assert response.status_code == 422
    assert password not in response.body.decode()
    assert "input" not in payload["errors"][0]
