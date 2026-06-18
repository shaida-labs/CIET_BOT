from datetime import UTC, datetime, timedelta
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import AdminUser


class Role(StrEnum):
    super_admin = "super_admin"
    admissions_admin = "admissions_admin"
    placement_admin = "placement_admin"
    content_admin = "content_admin"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, role: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdminUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        user_id = payload.get("sub")
    except JWTError as exc:
        raise credentials_error from exc
    if not user_id:
        raise credentials_error
    user = await session.scalar(select(AdminUser).where(AdminUser.id == user_id))
    if not user or not user.is_active:
        raise credentials_error
    return user


def require_roles(*roles: Role):
    async def guard(user: AdminUser = Depends(current_user)) -> AdminUser:
        if user.role not in roles and user.role != Role.super_admin:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return guard
