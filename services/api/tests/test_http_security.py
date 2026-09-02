import httpx
import pytest

from app.main import app


@pytest.mark.anyio
async def test_security_headers_are_present_and_server_banner_is_absent():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "server" not in response.headers
    assert response.headers["content-type"] == "application/json; charset=utf-8"


@pytest.mark.anyio
async def test_admin_cors_preflight_allows_csrf_header():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.options(
            "/api/v1/admin/faqs/example",
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
    assert response.status_code == 200
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.anyio
async def test_local_loopback_cors_preflight_is_allowed():
    """Opening the Docker UI with 127.0.0.1 must work as well as localhost."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.options(
            "/api/v1/chat",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


@pytest.mark.anyio
async def test_oversized_declared_api_body_is_rejected_before_parsing():
    transport = httpx.ASGITransport(app=app, client=("198.51.100.20", 4321))
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        response = await client.post(
            "/api/v1/chat",
            content=b"{}",
            headers={"Content-Length": "1000000", "Origin": "http://localhost:5173"},
        )
    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large"}


@pytest.mark.anyio
async def test_orchestrator_health_checks_are_not_rate_limited():
    transport = httpx.ASGITransport(app=app, client=("198.51.100.10", 4321))
    statuses = []
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        for _ in range(81):
            statuses.append((await client.get("/healthz")).status_code)
    assert statuses == [200] * 81
