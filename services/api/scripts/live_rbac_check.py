"""Credential-free RBAC acceptance check against the running local API.

Run inside the API container so tokens are signed with the active runtime secret:
`python -m scripts.live_rbac_check`.
"""

import asyncio
import uuid

import httpx
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.security import Role, create_access_token, hash_password
from app.db.session import SessionLocal, engine
from app.models import AdminUser


async def main() -> None:
    prefix = f"ciet-rbac-{uuid.uuid4()}"
    users = {
        role: AdminUser(
            email=f"{prefix}-{role.value}@local.invalid",
            password_hash=hash_password(str(uuid.uuid4())),
            role=role.value,
        )
        for role in Role
    }
    try:
        async with SessionLocal() as session:
            session.add_all(users.values())
            await session.commit()
        settings = get_settings()
        headers = {
            role: {
                "Authorization": f"Bearer {create_access_token(user.id, user.role, settings)}"
            }
            for role, user in users.items()
        }
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as client:
            checks = [
                ("public denied", "/api/v1/admin/faqs", {}, 401),
                ("admissions FAQ", "/api/v1/admin/faqs", headers[Role.admissions_admin], 200),
                ("admissions metric denied", "/api/v1/admin/metrics", headers[Role.admissions_admin], 403),
                # ROLE_PERMISSIONS grants admissions_admin manage_documents
                # (admissions uploads its own brochures), so read access is expected.
                ("admissions document", "/api/v1/admin/documents", headers[Role.admissions_admin], 200),
                ("placement metric", "/api/v1/admin/metrics", headers[Role.placement_admin], 200),
                ("placement FAQ denied", "/api/v1/admin/faqs", headers[Role.placement_admin], 403),
                ("placement document denied", "/api/v1/admin/documents", headers[Role.placement_admin], 403),
                ("content FAQ", "/api/v1/admin/faqs", headers[Role.content_admin], 200),
                ("content document", "/api/v1/admin/documents", headers[Role.content_admin], 200),
                ("content metric denied", "/api/v1/admin/metrics", headers[Role.content_admin], 403),
                ("admissions domain denied", "/api/v1/admin/domains", headers[Role.admissions_admin], 403),
                ("placement domain denied", "/api/v1/admin/domains", headers[Role.placement_admin], 403),
                ("content domain denied", "/api/v1/admin/domains", headers[Role.content_admin], 403),
                ("super FAQ", "/api/v1/admin/faqs", headers[Role.super_admin], 200),
                ("super metric", "/api/v1/admin/metrics", headers[Role.super_admin], 200),
                ("super document", "/api/v1/admin/documents", headers[Role.super_admin], 200),
                ("super domain", "/api/v1/admin/domains", headers[Role.super_admin], 200),
            ]
            results = []
            for name, path, request_headers, expected in checks:
                response = await client.get(path, headers=request_headers)
                if response.status_code != expected:
                    raise AssertionError(
                        f"{name}: expected {expected}, received {response.status_code}"
                    )
                results.append(f"{name}={expected}")

            mutation_checks = [
                (
                    "public metric mutation denied",
                    {},
                    {"name": "blocked", "value": "1", "verified_by": "none"},
                    401,
                ),
                (
                    "admissions metric mutation denied",
                    headers[Role.admissions_admin],
                    {"name": "blocked", "value": "1", "verified_by": "none"},
                    403,
                ),
                (
                    "content metric mutation denied",
                    headers[Role.content_admin],
                    {"name": "blocked", "value": "1", "verified_by": "none"},
                    403,
                ),
            ]
            for name, request_headers, payload, expected in mutation_checks:
                response = await client.post(
                    "/api/v1/admin/metrics", headers=request_headers, json=payload
                )
                if response.status_code != expected:
                    raise AssertionError(
                        f"{name}: expected {expected}, received {response.status_code}"
                    )
                results.append(f"{name}={expected}")
        print("Live RBAC passed: " + ", ".join(results))
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(AdminUser).where(AdminUser.email.like(f"{prefix}%")))
            await session.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
