from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, AuditLog


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
            metadata_=metadata or {},
        )
    )
