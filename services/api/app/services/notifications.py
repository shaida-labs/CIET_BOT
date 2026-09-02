import asyncio
import hashlib
import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.core.config import Settings


class NotificationError(RuntimeError):
    pass


class NotificationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_password_reset(self, email: str, token: str) -> None:
        await self._send(email, "Reset your CIET AI administrator password", f"{self.settings.admin_origin}/reset-password?token={token}")

    async def send_invitation(self, email: str, token: str) -> None:
        await self._send(email, "CIET AI administrator invitation", f"{self.settings.admin_origin}/accept-invitation?token={token}")

    async def _send(self, recipient: str, subject: str, link: str) -> None:
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(f"Use this single-use link before it expires:\n{link}\n")
        if self.settings.smtp_host:
            if not self.settings.smtp_from:
                raise NotificationError("SMTP_FROM is required when SMTP is configured")
            message["From"] = self.settings.smtp_from
            try:
                await asyncio.to_thread(self._send_smtp, message)
            except (OSError, smtplib.SMTPException) as exc:
                raise NotificationError("Unable to send account email") from exc
            return
        if self.settings.environment != "local":
            raise NotificationError("Email delivery is not configured")
        outbox = Path(self.settings.local_storage_path).resolve().parent / "mail-outbox"
        outbox.mkdir(mode=0o700, parents=True, exist_ok=True)
        message_path = outbox / f"{hashlib.sha256(recipient.encode('utf-8')).hexdigest()}.eml"
        message_path.write_bytes(message.as_bytes())
        message_path.chmod(0o600)

    def _send_smtp(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
            client.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(message)
