import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.core.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    create_access_token,
    current_user,
    hash_one_time_token,
    hash_password,
    new_csrf_token,
    new_one_time_token,
    new_otp_code,
    validate_password,
    verify_password,
)
from app.db.session import get_session
from app.models import AdminInvitation, AdminOtpChallenge, AdminUser, PasswordResetToken, now
from app.schemas import (
    AcceptInvitationIn,
    AdminInvitationIn,
    AuthSessionOut,
    ChangePasswordIn,
    ForgotPasswordIn,
    GenericMessageOut,
    LoginIn,
    OtpRequestIn,
    OtpVerifyIn,
    ResetPasswordIn,
)
from app.services.audit import write_audit
from app.services.notifications import NotificationError, NotificationService

router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookies(response: Response, token: str, settings: Settings) -> None:
    csrf_token = new_csrf_token()
    cookie_options = {
        "secure": settings.secure_cookies,
        "samesite": "strict",
        "max_age": settings.access_token_minutes * 60,
        "path": "/",
    }
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, **cookie_options)
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        domain=settings.csrf_cookie_domain,
        **cookie_options,
    )


@router.post("/login", response_model=AuthSessionOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthSessionOut:
    email = payload.email.strip().lower()
    user = await session.scalar(select(AdminUser).where(AdminUser.email == email).with_for_update())
    current_time = now()
    if (
        not user
        or not user.is_active
        or (user.locked_until and user.locked_until > current_time)
        or not verify_password(payload.password, user.password_hash)
    ):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_failures:
                user.locked_until = current_time + timedelta(minutes=settings.login_lock_minutes)
            await write_audit(session, action="login_failure", entity_type="admin_user", entity_id=user.id, user=user, request=request)
            await session.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    active_challenges = list(
        (
            await session.scalars(
                select(AdminOtpChallenge).where(
                    AdminOtpChallenge.admin_user_id == user.id,
                    AdminOtpChallenge.used_at.is_(None),
                )
            )
        ).all()
    )
    for challenge in active_challenges:
        challenge.used_at = current_time

    challenge_token = new_one_time_token()
    code = new_otp_code()
    session.add(
        AdminOtpChallenge(
            admin_user_id=user.id,
            challenge_hash=hash_one_time_token(challenge_token),
            code_hash=hash_one_time_token(code),
            expires_at=current_time + timedelta(minutes=settings.otp_expiry_minutes),
            max_attempts=settings.otp_max_attempts,
            resend_after=current_time + timedelta(seconds=settings.otp_resend_seconds),
        )
    )
    await write_audit(session, action="otp_requested", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    try:
        await NotificationService(settings).send_otp(user.email, code)
    except NotificationError as exc:
        raise HTTPException(status_code=503, detail="BLOCKED - EXTERNAL CONFIGURATION REQUIRED") from exc
    return AuthSessionOut(email=user.email, challenge=challenge_token, otp_required=True)


@router.post("/otp/request", response_model=AuthSessionOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def request_otp(
    payload: OtpRequestIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthSessionOut:
    challenge = await session.scalar(
        select(AdminOtpChallenge)
        .where(
            AdminOtpChallenge.challenge_hash == hash_one_time_token(payload.challenge),
            AdminOtpChallenge.used_at.is_(None),
            AdminOtpChallenge.expires_at > now(),
        )
        .with_for_update()
    )
    if not challenge or challenge.resend_after > now():
        raise HTTPException(status_code=429, detail="A verification code cannot be resent yet")
    user = await session.get(AdminUser, challenge.admin_user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Verification challenge is invalid or expired")
    code = new_otp_code()
    challenge.code_hash = hash_one_time_token(code)
    challenge.attempts = 0
    challenge.expires_at = now() + timedelta(minutes=settings.otp_expiry_minutes)
    challenge.resend_after = now() + timedelta(seconds=settings.otp_resend_seconds)
    await write_audit(session, action="otp_requested", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    try:
        await NotificationService(settings).send_otp(user.email, code)
    except NotificationError as exc:
        raise HTTPException(status_code=503, detail="BLOCKED - EXTERNAL CONFIGURATION REQUIRED") from exc
    return AuthSessionOut(email=user.email, challenge=payload.challenge, otp_required=True)


@router.post("/otp/verify", response_model=AuthSessionOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def verify_otp(
    payload: OtpVerifyIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthSessionOut:
    challenge = await session.scalar(
        select(AdminOtpChallenge)
        .where(
            AdminOtpChallenge.challenge_hash == hash_one_time_token(payload.challenge),
            AdminOtpChallenge.used_at.is_(None),
            AdminOtpChallenge.expires_at > now(),
        )
        .with_for_update()
    )
    if not challenge:
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")
    user = await session.get(AdminUser, challenge.admin_user_id, with_for_update=True)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")
    if not secrets.compare_digest(challenge.code_hash, hash_one_time_token(payload.code)):
        challenge.attempts += 1
        if challenge.attempts >= challenge.max_attempts:
            challenge.used_at = now()
        await write_audit(session, action="otp_verification_failure", entity_type="admin_user", entity_id=user.id, user=user, request=request)
        await session.commit()
        raise HTTPException(status_code=401, detail="Verification code is invalid")

    challenge.used_at = now()
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    await write_audit(session, action="otp_verification_success", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await write_audit(session, action="login_success", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    token = create_access_token(user.id, user.role, settings, session_version=user.session_version)
    set_auth_cookies(response, token, settings)
    return AuthSessionOut(email=user.email, role=user.role)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    user: AdminUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    user.session_version += 1
    await write_audit(
        session,
        action="logout",
        entity_type="admin_user",
        entity_id=user.id,
        user=user,
        request=request,
    )
    await session.commit()
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/", domain=settings.csrf_cookie_domain)


@router.get("/session", response_model=AuthSessionOut)
async def session_status(user: AdminUser = Depends(current_user)) -> AuthSessionOut:
    return AuthSessionOut(email=user.email, role=user.role)


@router.post("/change-password", response_model=GenericMessageOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def change_password(
    payload: ChangePasswordIn,
    request: Request,
    user: AdminUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> GenericMessageOut:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    try:
        validate_password(payload.new_password)
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user.session_version += 1
    await write_audit(session, action="change_password", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    return GenericMessageOut(message="Password changed. Please sign in again.")


@router.post("/forgot-password", response_model=GenericMessageOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def forgot_password(
    payload: ForgotPasswordIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> GenericMessageOut:
    message = GenericMessageOut(message="If the account exists, a reset link has been sent.")
    user = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email.strip().lower(), AdminUser.is_active.is_(True)))
    if not user:
        return message
    token = new_one_time_token()
    reset = PasswordResetToken(
        admin_user_id=user.id,
        token_hash=hash_one_time_token(token),
        expires_at=now() + timedelta(minutes=settings.password_reset_minutes),
    )
    session.add(reset)
    await write_audit(session, action="password_reset_requested", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    try:
        await NotificationService(settings).send_password_reset(user.email, token)
    except NotificationError:
        # The public response remains intentionally indistinguishable to prevent user enumeration.
        return message
    return message


@router.post("/reset-password", response_model=GenericMessageOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def reset_password(
    payload: ResetPasswordIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GenericMessageOut:
    try:
        validate_password(payload.new_password)
        password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reset = await session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_one_time_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now(),
        )
        .with_for_update()
    )
    if not reset:
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired")
    user = await session.get(AdminUser, reset.admin_user_id, with_for_update=True)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired")
    user.password_hash = password_hash
    user.session_version += 1
    reset.used_at = now()
    await write_audit(session, action="password_reset", entity_type="admin_user", entity_id=user.id, user=user, request=request)
    await session.commit()
    return GenericMessageOut(message="Password reset. Please sign in.")


@router.post("/invitations", response_model=GenericMessageOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def create_invitation(
    payload: AdminInvitationIn,
    request: Request,
    user: AdminUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> GenericMessageOut:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    email = payload.email.strip().lower()
    if await session.scalar(select(AdminUser.id).where(AdminUser.email == email)):
        raise HTTPException(status_code=409, detail="An administrator with this email already exists")
    token = new_one_time_token()
    invitation = AdminInvitation(
        name=payload.name,
        email=email,
        role=payload.role,
        invited_by_id=user.id,
        token_hash=hash_one_time_token(token),
        expires_at=now() + timedelta(hours=settings.invitation_expiry_hours),
    )
    session.add(invitation)
    await session.flush()
    await write_audit(session, action="admin_invited", entity_type="admin_invitation", entity_id=invitation.id, user=user, request=request, metadata={"email": email, "role": payload.role})
    await session.commit()
    try:
        await NotificationService(settings).send_invitation(email, token)
    except NotificationError as exc:
        raise HTTPException(status_code=503, detail="Invitation email could not be delivered") from exc
    return GenericMessageOut(message="Administrator invitation sent.")


@router.post("/accept-invitation", response_model=GenericMessageOut)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def accept_invitation(
    payload: AcceptInvitationIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> GenericMessageOut:
    try:
        validate_password(payload.password)
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    invitation = await session.scalar(
        select(AdminInvitation)
        .where(
            AdminInvitation.token_hash == hash_one_time_token(payload.token),
            AdminInvitation.accepted_at.is_(None),
            AdminInvitation.expires_at > now(),
        )
        .with_for_update()
    )
    if not invitation:
        raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
    if await session.scalar(select(AdminUser.id).where(AdminUser.email == invitation.email)):
        raise HTTPException(status_code=409, detail="An administrator with this email already exists")
    new_user = AdminUser(email=invitation.email, name=payload.name or invitation.name, password_hash=password_hash, role=invitation.role, is_active=True)
    session.add(new_user)
    await session.flush()
    invitation.accepted_at = now()
    await write_audit(session, action="admin_invitation_accepted", entity_type="admin_user", entity_id=new_user.id, user=new_user, request=request)
    await session.commit()
    return GenericMessageOut(message="Administrator account activated. Please sign in.")
