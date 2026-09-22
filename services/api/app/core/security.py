import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import AdminUser


class Role(StrEnum):
    super_admin = "super_admin"
    admin = "admin"
    viewer = "viewer"
    admissions_admin = "admissions_admin"
    placement_admin = "placement_admin"
    content_admin = "content_admin"


class Permission(StrEnum):
    view_analytics = "view_analytics"
    manage_faqs = "manage_faqs"
    manage_metrics = "manage_metrics"
    manage_documents = "manage_documents"
    view_conversations = "view_conversations"
    manage_admins = "manage_admins"
    manage_security = "manage_security"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    Role.super_admin: frozenset(Permission),
    Role.admin: frozenset(Permission),
    Role.viewer: frozenset({Permission.view_analytics, Permission.view_conversations}),
    Role.admissions_admin: frozenset({Permission.view_analytics, Permission.manage_faqs, Permission.manage_documents}),
    Role.placement_admin: frozenset({Permission.view_analytics, Permission.manage_metrics}),
    Role.content_admin: frozenset({Permission.view_analytics, Permission.manage_faqs, Permission.manage_documents}),
    "director": frozenset(Permission),
    "hod": frozenset({Permission.view_analytics, Permission.manage_faqs, Permission.manage_documents}),
    "bot_maintenance": frozenset({Permission.view_analytics, Permission.manage_documents, Permission.manage_security}),
    "content_manager": frozenset({Permission.view_analytics, Permission.manage_faqs, Permission.manage_documents}),
    "auditor": frozenset({Permission.view_analytics, Permission.view_conversations}),
}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ACCESS_COOKIE = "ciet_access_token"
CSRF_COOKIE = "ciet_csrf_token"


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (TypeError, ValueError):
        return False


def validate_password(password: str) -> None:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    character_classes = sum(
        (
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        )
    )
    if len(password) < 12 or character_classes < 3:
        raise ValueError("Password must be at least 12 characters and use three character types")


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_one_time_token() -> str:
    return secrets.token_urlsafe(48)


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_access_token(
    subject: str,
    role: str,
    settings: Settings | None = None,
    *,
    session_version: int = 0,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "ver": session_version,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdminUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        cookie_token = request.cookies.get(ACCESS_COOKIE)
        token = bearer_token or cookie_token
        if not token:
            raise credentials_error
        if not bearer_token and request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf_cookie = request.cookies.get(CSRF_COOKIE)
            csrf_header = request.headers.get("X-CSRF-Token")
            if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
                raise HTTPException(status_code=403, detail="CSRF validation failed")
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        user_id = payload.get("sub")
        token_version = payload.get("ver")
    except InvalidTokenError as exc:
        raise credentials_error from exc
    if not user_id:
        raise credentials_error
    user = await session.scalar(select(AdminUser).where(AdminUser.id == user_id))
    if (
        not user
        or not user.is_active
        or not isinstance(token_version, int)
        or token_version != user.session_version
    ):
        raise credentials_error
    return user


def require_roles(*roles: Role):
    async def guard(request: Request, user: AdminUser = Depends(current_user)) -> AdminUser:
        if user.role in {Role.super_admin, Role.admin}:
            return user
        if user.role == Role.viewer and Role.super_admin not in roles and request.method in {"GET", "HEAD"}:
            return user
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return guard


def require_permissions(*permissions: Permission):
    async def guard(_: Request, user: AdminUser = Depends(current_user)) -> AdminUser:
        granted = ROLE_PERMISSIONS.get(user.role, frozenset())
        if not set(permissions).issubset(granted):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return guard
