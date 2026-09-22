from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, AuditLog

SENSITIVE_METADATA_KEYS = ("password", "secret", "token", "authorization", "api_key", "api-key")


def sanitize_audit_metadata(value, *, key: str = ""):
    if any(term in key.casefold() for term in SENSITIVE_METADATA_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize_audit_metadata(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_audit_metadata(item, key=key) for item in value]
    return value


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user: AdminUser | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=request.client.host if request and request.client else None,
            metadata_=sanitize_audit_metadata(metadata or {}),
        )
    )
