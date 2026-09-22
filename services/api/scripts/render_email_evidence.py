"""Render the real administrator emails as standalone HTML for visual review.

The OTP message is parsed from the on-disk mail-outbox when one exists (the
exact bytes the delivery path wrote); invitation and password-reset messages
are built by the same NotificationService code the API calls. Output feeds
e2e/email-evidence.mjs, which screenshots each file into qa_evidence/emails/.

Usage: .venv\\Scripts\\python -m scripts.render_email_evidence
"""

import asyncio
import subprocess
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from app.core.config import Settings
from app.services.notifications import NotificationService

OUTBOX = Path(__file__).resolve().parents[1] / "storage" / "mail-outbox"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "qa_evidence" / "emails"


class _Capture(NotificationService):
    """Service that keeps the message instead of delivering it."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.sent = []

    async def _deliver(self, message: EmailMessage) -> None:
        self.sent.append(message)


def html_part(message: EmailMessage) -> str:
    body = message.get_body(preferencelist=("html",))
    assert body is not None, "message has no HTML part"
    return body.get_content()


def parse_html(raw: bytes) -> str | None:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    body = message.get_body(preferencelist=("html",))
    return body.get_content() if body is not None else None


def newest_outbox_email() -> str | None:
    """Newest delivered OTP email: host outbox first, then the Docker volume."""
    if OUTBOX.is_dir():
        candidates = sorted(OUTBOX.glob("*.eml"), key=lambda path: path.stat().st_mtime)
        if candidates:
            parsed = parse_html(candidates[-1].read_bytes())
            if parsed is not None:
                return parsed
    # The stack stores /app/storage in a named volume; read the newest message
    # straight from the container, the same way e2e/live-readiness.mjs does.
    try:
        result = subprocess.run(
            [
                "docker", "compose", "exec", "-T", "api", "sh", "-c",
                "f=$(ls -t /app/storage/mail-outbox/*.eml 2>/dev/null | head -1); [ -n \"$f\" ] && cat \"$f\"",
            ],
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout:
        parsed = parse_html(result.stdout)
        if parsed is not None:
            return parsed
    return None


async def main() -> None:
    out_dir = DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in (*out_dir.glob("*.html"), *out_dir.glob("*.png")):
        stale.unlink()
    settings = Settings(
        widget_origin="http://localhost:8080",
        admin_origin="http://localhost:8080",
    )

    written = []

    delivered = newest_outbox_email()
    if delivered:
        (out_dir / "otp-delivered.html").write_text(delivered, encoding="utf-8")
        written.append("otp-delivered.html (parsed from the real mail-outbox)")
    else:
        service = _Capture(settings)
        await service.send_otp("admin@example.edu", "123456")
        (out_dir / "otp-rendered.html").write_text(html_part(service.sent[0]), encoding="utf-8")
        written.append("otp-rendered.html (no outbox email present)")

    service = _Capture(settings)
    await service.send_invitation("admin@example.edu", "evidence-invite-token")
    (out_dir / "invitation.html").write_text(html_part(service.sent[0]), encoding="utf-8")
    written.append("invitation.html")

    service = _Capture(settings)
    await service.send_password_reset("admin@example.edu", "evidence-reset-token")
    (out_dir / "password-reset.html").write_text(html_part(service.sent[0]), encoding="utf-8")
    written.append("password-reset.html")

    for name in written:
        print(out_dir / name.split(" ")[0])


if __name__ == "__main__":
    asyncio.run(main())
