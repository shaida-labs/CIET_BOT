"""Provision or remove the reserved live-E2E administrator in local mode only."""

import argparse
import asyncio

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.security import Role, hash_password
from app.db.session import SessionLocal, engine
from app.models import AdminUser, AuditLog

EMAIL = "ciet-e2e@local.invalid"
PASSWORD = "CIET-e2e-password-2026!"


async def main(action: str) -> None:
    if get_settings().environment != "local":
        raise RuntimeError("The E2E administrator helper is restricted to local environments")
    async with SessionLocal() as session:
        if action == "create":
            user = await session.scalar(select(AdminUser).where(AdminUser.email == EMAIL))
            if user is None:
                user = AdminUser(email=EMAIL, password_hash=hash_password(PASSWORD))
                session.add(user)
            else:
                user.password_hash = hash_password(PASSWORD)
            user.role = Role.super_admin.value
            user.is_active = True
            user.session_version = (user.session_version or 0) + 1
        else:
            user = await session.scalar(select(AdminUser).where(AdminUser.email == EMAIL))
            if user is not None:
                await session.execute(delete(AuditLog).where(AuditLog.actor_id == user.id))
            await session.execute(delete(AdminUser).where(AdminUser.email == EMAIL))
        await session.commit()
    await engine.dispose()
    print(f"Local E2E administrator {action} complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "delete"))
    args = parser.parse_args()
    asyncio.run(main(args.action))
