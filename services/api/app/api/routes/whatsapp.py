import hashlib
import hmac
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import WhatsAppDelivery
from app.services.language import detect_language
from app.workers.tasks import process_whatsapp_message

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def webhook_values(payload: object) -> list[dict]:
    """Return well-formed Meta value objects and reject an invalid envelope."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid WhatsApp payload")
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        raise HTTPException(status_code=422, detail="Invalid WhatsApp payload")
    values: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if isinstance(change, dict) and isinstance(change.get("value"), dict):
                values.append(change["value"])
    return values


def inbound_claim_statement(message_id: str, sender: str, message_type: str):
    return (
        insert(WhatsAppDelivery)
        .values(
            provider_message_id=message_id,
            recipient=sender,
            status="queued",
            payload={"direction": "inbound", "type": message_type},
        )
        .on_conflict_do_nothing(index_elements=["provider_message_id"])
        .returning(WhatsAppDelivery.id)
    )


def verify_signature(body: bytes, signature: str | None, settings: Settings) -> None:
    if not settings.whatsapp_app_secret:
        raise HTTPException(status_code=503, detail="WhatsApp integration is not configured")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing WhatsApp signature")
    digest = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={digest}", signature):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return hub_challenge or ""
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    body = await request.body()
    verify_signature(body, x_hub_signature_256, settings)
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid WhatsApp payload") from exc
    values = webhook_values(payload)
    jobs: list[tuple[str, str, str, str]] = []
    async for session in get_session():
        for value in values:
            messages = value.get("messages", [])
            statuses = value.get("statuses", [])
            if not isinstance(messages, list) or not isinstance(statuses, list):
                continue
            for message in messages:
                if not isinstance(message, dict):
                    continue
                message_type = message.get("type", "text")
                text_payload = message.get("text", {})
                text = text_payload.get("body") if isinstance(text_payload, dict) else None
                sender = message.get("from")
                message_id = message.get("id")
                if not sender or not message_id:
                    continue
                inbound_id = await session.scalar(
                    inbound_claim_statement(message_id, sender, message_type)
                )
                if not inbound_id:
                    continue
                if message_type in {"document", "image"} and not text:
                    text = (
                        "A document or media message was received on WhatsApp. "
                        "Please ask a text question, or upload official documents in the admin dashboard."
                    )
                if not text:
                    await session.execute(
                        update(WhatsAppDelivery)
                        .where(WhatsAppDelivery.id == inbound_id)
                        .values(status="ignored")
                    )
                    continue
                jobs.append((str(inbound_id), sender, text, detect_language(text)))
            for status in statuses:
                if not isinstance(status, dict):
                    continue
                provider_id = status.get("id")
                if provider_id:
                    existing = await session.scalar(
                        select(WhatsAppDelivery).where(WhatsAppDelivery.provider_message_id == provider_id)
                    )
                    if existing:
                        existing.status = status.get("status", existing.status)
                    else:
                        session.add(
                            WhatsAppDelivery(
                                provider_message_id=provider_id,
                                recipient=status.get("recipient_id", "unknown"),
                                status=status.get("status", "unknown"),
                                payload=status,
                            )
                        )
        await session.commit()
    for inbound_id, sender, text, language in jobs:
        process_whatsapp_message.delay(inbound_id, sender, text, language)
    return {"status": "ok"}
