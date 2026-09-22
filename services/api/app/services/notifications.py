import asyncio
import hashlib
import smtplib
from email.message import EmailMessage
from pathlib import Path

from app.core.config import Settings
from app.services.email_templates import logo_url, render_email_html


class NotificationError(RuntimeError):
    pass


class NotificationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_password_reset(self, email: str, token: str) -> None:
        link = f"{self.settings.admin_origin}/reset-password?token={token}"
        await self._send(
            email,
            subject="Reset your CIET AI administrator password",
            heading="Reset your administrator password",
            intro="We received a request to reset the password of your CIET AI administrator account.",
            cta_label="Choose a new password",
            cta_url=link,
            note=(
                "This single-use link expires soon. If you did not request it, you can safely ignore "
                "this email and your password stays unchanged."
            ),
            plain=f"Use this single-use link before it expires:\n{link}\n",
        )

    async def send_invitation(self, email: str, token: str) -> None:
        link = f"{self.settings.admin_origin}/accept-invitation?token={token}"
        await self._send(
            email,
            subject="CIET AI administrator invitation",
            heading="You are invited as an administrator",
            intro="An administrator seat for the CIET AI Assistant console has been reserved for your email address.",
            cta_label="Accept the invitation",
            cta_url=link,
            note=(
                "This invitation is single-use and expires soon. Accept it only if you were expecting "
                "this email from your CIET administrator."
            ),
            plain=f"Use this single-use link before it expires:\n{link}\n",
        )

    async def send_otp(self, email: str, code: str) -> None:
        expiry = self.settings.otp_expiry_minutes
        message = self._build_message(
            email,
            subject="Your CIET AI administrator verification code",
            plain=(
                f"Your CIET AI administrator verification code is {code}. "
                f"It expires in {expiry} minutes and can be used once.\n"
            ),
            html=render_email_html(
                logo=logo_url(self.settings.widget_origin),
                heading="Your sign-in verification code",
                intro=(
                    f"Enter this code to finish signing in to the CIET AI administrator console. "
                    f"It expires in {expiry} minutes and can be used once."
                ),
                code=code,
                note="Never share this code \u2014 CIET staff will never ask for it.",
            ),
        )
        await self._deliver(message)

    async def _send(
        self,
        recipient: str,
        *,
        subject: str,
        heading: str,
        intro: str,
        cta_label: str,
        cta_url: str,
        note: str,
        plain: str,
    ) -> None:
        html = render_email_html(
            logo=logo_url(self.settings.widget_origin),
            heading=heading,
            intro=intro,
            cta_label=cta_label,
            cta_url=cta_url,
            note=note,
        )
        await self._deliver(self._build_message(recipient, subject=subject, plain=plain, html=html))

    def _build_message(self, recipient: str, *, subject: str, plain: str, html: str) -> EmailMessage:
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(plain)
        message.add_alternative(html, subtype="html")
        return message

    async def _deliver(self, message: EmailMessage) -> None:
        """Deliver a real message over configured SMTP.

        Staging and production require real SMTP and fail closed when it is not
        configured. Only ENVIRONMENT=local may fall back to the on-disk
        mail-outbox (the same real message bytes, written instead of relayed),
        so local development and CI can read the exact email a production
        deployment would have sent. There is no simulated delivery path.
        """
        recipient = message["To"]
        if self.settings.smtp_host:
            await self._send_smtp_message(message)
            return
        if self.settings.environment != "local":
            raise NotificationError("Email delivery is not configured")
        outbox = Path(self.settings.local_storage_path).resolve().parent / "mail-outbox"
        outbox.mkdir(mode=0o700, parents=True, exist_ok=True)
        message_path = outbox / f"{hashlib.sha256(recipient.encode('utf-8')).hexdigest()}.eml"
        message_path.write_bytes(message.as_bytes())
        message_path.chmod(0o600)

    async def _send_smtp_message(self, message: EmailMessage) -> None:
        from_email = self.settings.smtp_from_email or self.settings.smtp_from
        if not from_email:
            raise NotificationError("SMTP_FROM_EMAIL is required when SMTP is configured")
        message["From"] = f"{self.settings.smtp_from_name} <{from_email}>"
        try:
            await asyncio.to_thread(self._send_smtp, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotificationError("Unable to send account email") from exc

    def _send_smtp(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
            client.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(message)
