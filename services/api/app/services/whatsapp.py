import asyncio

import httpx

from app.core.config import Settings
from app.models import WhatsAppDelivery


async def send_whatsapp_message(settings: Settings, to: str, text: str) -> WhatsAppDelivery:
    """Send one bounded outbound reply; callers decide whether a failure retries."""
    delivery = WhatsAppDelivery(recipient=to, status="not_configured", payload={"body": text[:3900]})
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        delivery.error_message = "WhatsApp delivery is not configured"
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
                delivery.provider_message_id = (data.get("messages") or [{}])[0].get("id")
                delivery.status = "sent"
                delivery.payload = data
                return delivery
            except (httpx.HTTPError, ValueError) as exc:
                delivery.status = "failed"
                delivery.error_message = f"{type(exc).__name__}: delivery failed"
                if attempt < 3:
                    await asyncio.sleep(0.5 * attempt)
    return delivery
