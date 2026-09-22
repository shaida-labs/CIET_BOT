"""Premium email contract: branded multipart HTML plus a parseable text fallback."""

import re

import pytest

from app.core.config import Settings
from app.services.email_templates import logo_url, render_email_html
from app.services.notifications import NotificationService

RECIPIENT = "admin@example.edu"
ORIGIN = "https://ciet.example.edu"


@pytest.fixture
def delivered(monkeypatch):
    """Capture the exact EmailMessage each sender hands to delivery."""
    messages = []

    async def capture(self, message):
        messages.append(message)

    monkeypatch.setattr(NotificationService, "_deliver", capture)
    return messages


def service() -> NotificationService:
    return NotificationService(
        Settings(jwt_secret="x" * 32, widget_origin=ORIGIN, admin_origin=ORIGIN),
    )


def html_of(message) -> str:
    part = message.get_body(preferencelist=("html",))
    assert part is not None, "email must include an HTML alternative"
    return part.get_content()


def plain_of(message) -> str:
    part = message.get_body(preferencelist=("plain",))
    assert part is not None, "email must include a plain-text fallback"
    return part.get_content()


def assert_premium_shell(message) -> None:
    assert message.get_content_type() == "multipart/alternative"
    html = html_of(message)
    assert html.lower().startswith("<!doctype html>")
    # College logo, wordmark, brand accent, card layout, and trust footer.
    assert f"{ORIGIN}/ciet-logo.jpg" in html
    assert "Chalapathi Institute of" in html
    assert "Engineering &amp; Technology" in html
    assert "#0b5cad" in html
    assert "<h1" in html
    assert "automated security message" in html


@pytest.mark.anyio
async def test_otp_email_is_premium_and_keeps_the_live_e2e_code_regex(delivered):
    await service().send_otp(RECIPIENT, "123456")

    assert len(delivered) == 1
    message = delivered[0]
    assert message["To"] == RECIPIENT
    assert message["Subject"] == "Your CIET AI administrator verification code"
    assert_premium_shell(message)

    html = html_of(message)
    assert ">123456<" in html  # Large verification-code panel.
    assert "Verification code" in html

    # live-readiness E2E parses this exact phrase from the on-disk .eml bytes.
    match = re.search(r"verification code is (\d{6})", plain_of(message))
    assert match is not None and match.group(1) == "123456"
    raw = message.as_bytes().decode("utf-8", errors="replace")
    assert re.search(r"verification code is (\d{6})", raw) is not None


@pytest.mark.anyio
async def test_invitation_email_is_premium_with_cta_and_raw_link(delivered):
    await service().send_invitation(RECIPIENT, "invite-token-123")

    message = delivered[0]
    assert message["Subject"] == "CIET AI administrator invitation"
    assert_premium_shell(message)

    link = f"{ORIGIN}/accept-invitation?token=invite-token-123"
    html = html_of(message)
    assert f'href="{link}"' in html
    assert "Accept the invitation" in html

    plain = plain_of(message)
    assert "Use this single-use link before it expires:" in plain
    assert link in plain


@pytest.mark.anyio
async def test_password_reset_email_is_premium_with_cta_and_raw_link(delivered):
    await service().send_password_reset(RECIPIENT, "reset-token-456")

    message = delivered[0]
    assert message["Subject"] == "Reset your CIET AI administrator password"
    assert_premium_shell(message)

    link = f"{ORIGIN}/reset-password?token=reset-token-456"
    html = html_of(message)
    assert f'href="{link}"' in html
    assert "Choose a new password" in html

    plain = plain_of(message)
    assert "Use this single-use link before it expires:" in plain
    assert link in plain


def test_logo_url_joins_origin_without_double_slash():
    assert logo_url("https://ciet.example.edu") == "https://ciet.example.edu/ciet-logo.jpg"
    assert logo_url("https://ciet.example.edu/") == "https://ciet.example.edu/ciet-logo.jpg"


def test_email_template_escapes_caller_supplied_text():
    html = render_email_html(
        logo=logo_url(ORIGIN),
        heading="<script>alert(1)</script>",
        intro="fees & placements",
        note="note",
        code='"><img src=x>',
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "fees &amp; placements" in html
    assert "&quot;&gt;&lt;img" in html
