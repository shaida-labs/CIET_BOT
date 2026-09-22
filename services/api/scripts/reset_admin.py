"""Provision or reset one local administrator without exposing a password.

This command is deliberately CLI-only and restricted to ENVIRONMENT=local.
It never accepts passwords as command-line arguments or prints them.
"""

import argparse
import asyncio
import getpass
import re

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import Role, hash_password, validate_password
from app.db.session import SessionLocal, engine
from app.models import AdminUser

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def read_password() -> str:
    password = getpass.getpass("Admin password (input hidden): ")
    confirmation = getpass.getpass("Confirm admin password (input hidden): ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    validate_password(password)
    return password


async def main(email: str, name: str) -> None:
    settings = get_settings()
    if settings.environment != "local":
        raise RuntimeError("This provisioning command is restricted to ENVIRONMENT=local")
    email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("A valid administrator email is required")
    password = read_password()

    async with SessionLocal() as session:
        user = await session.scalar(select(AdminUser).where(AdminUser.email == email).with_for_update())
        action = "updated"
        if user is None:
            user = AdminUser(email=email, name=name.strip() or "CIET Administrator")
            session.add(user)
            action = "created"
        user.name = name.strip() or user.name or "CIET Administrator"
        user.password_hash = hash_password(password)
        user.role = Role.super_admin.value
        user.is_active = True
        user.failed_login_count = 0
        user.locked_until = None
        user.session_version = (user.session_version or 0) + 1
        await session.commit()
    print(f"Local administrator {action}: {email}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision or reset a local CIET administrator")
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--name", default="CIET Administrator", help="Administrator display name")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.email, args.name))
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
