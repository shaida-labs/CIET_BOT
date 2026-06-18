import hashlib
import hmac
import asyncio

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import WhatsAppDelivery
from app.schemas import ChatRequest
from app.api.routes.chat import chat
from app.services.language import detect_language

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def verify_signature(body: bytes, signature: str | None, settings: Settings) -> None:
    if not settings.whatsapp_app_secret:
        return
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
    payload = await request.json()
    entries = payload.get("entry", [])
    async for session in get_session():
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    message_type = message.get("type", "text")
                    text = message.get("text", {}).get("body")
                    sender = message.get("from")
                    if not sender:
                        continue
                    if message_type in {"document", "image"} and not text:
                        text = (
                            "A document or media message was received on WhatsApp. "
                            "Please ask a text question, or upload official documents in the admin dashboard."
                        )
                    if not text:
                        continue
                    response = await chat(
                        ChatRequest(message=text, channel="whatsapp", user_ref=sender, language=detect_language(text)),
                        request,
                        session,
                        settings,
                    )
                    delivery = await send_whatsapp_message(settings, sender, response.message.content)
                    session.add(delivery)
            for status in value.get("statuses", []):
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
    return {"status": "ok"}


async def send_whatsapp_message(settings: Settings, to: str, text: str) -> WhatsAppDelivery:
    delivery = WhatsAppDelivery(recipient=to, status="skipped", payload={"body": text[:3900]})
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return delivery
    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:3900]},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in range(1, 4):
            delivery.attempts = attempt
            try:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                provider_id = (data.get("messages") or [{}])[0].get("id")
                delivery.provider_message_id = provider_id
                delivery.status = "sent"
                delivery.payload = data
                return delivery
            except httpx.HTTPError as exc:
                delivery.status = "failed"
                delivery.error_message = str(exc)
                if attempt < 3:
                    await asyncio.sleep(0.5 * attempt)
    return delivery
