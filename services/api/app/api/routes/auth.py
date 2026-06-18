from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models import AdminUser
from app.schemas import LoginIn, TokenOut
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    user = await session.scalar(select(AdminUser).where(AdminUser.email == payload.username.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await write_audit(session, action="login", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.post("/bootstrap", response_model=TokenOut)
async def bootstrap(
    payload: LoginIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    existing = await session.scalar(select(AdminUser))
    if existing:
        raise HTTPException(status_code=409, detail="Admin already exists")
    user = AdminUser(
        email=payload.username.lower(),
        password_hash=hash_password(payload.password),
        role="super_admin",
    )
    session.add(user)
    await session.flush()
    await write_audit(session, action="bootstrap", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    await session.refresh(user)
    return TokenOut(access_token=create_access_token(user.id, user.role))
