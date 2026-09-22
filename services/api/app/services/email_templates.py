"""Premium HTML email rendering for CIET AI administrator notifications.

Every message is a self-contained multipart email: a branded HTML part
(responsive table layout, inline styles, college logo and wordmark) plus the
plain-text fallback that carries the same actionable content. The layout
degrades gracefully when a client blocks remote images or ignores modern CSS:
the college name stays visible as text next to the logo, and buttons fall back
to a raw link underneath.
"""

from html import escape

COLLEGE_NAME = "Chalapathi Institute of Engineering & Technology"
BRAND_ACCENT = "#0b5cad"  # Same primary color the chat widget ships with.


def logo_url(widget_origin: str) -> str:
    """Absolute URL of the college logo served by the web container."""
    return f"{str(widget_origin).rstrip('/')}/ciet-logo.jpg"


def _code_panel(code: str) -> str:
    return f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 6px 0;background-color:#f8fafc;border:1px dashed #94a3b8;border-radius:12px;">
              <tr>
                <td align="center" style="padding:20px 16px;">
                  <div style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#64748b;margin-bottom:8px;">Verification code</div>
                  <div style="font-family:'Courier New',Courier,monospace;font-size:34px;font-weight:bold;letter-spacing:8px;color:#0f172a;padding-left:8px;">{escape(code)}</div>
                </td>
              </tr>
            </table>"""


def _cta_panel(label: str, url: str) -> str:
    href = escape(url, quote=True)
    return f"""
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0;">
              <tr>
                <td align="center" bgcolor="{BRAND_ACCENT}" style="border-radius:10px;background-color:{BRAND_ACCENT};">
                  <a href="{href}" style="display:inline-block;padding:14px 30px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;border-radius:10px;">{escape(label)}</a>
                </td>
              </tr>
            </table>
            <p style="margin:0 0 4px 0;font-size:13px;line-height:1.6;color:#64748b;word-break:break-all;">If the button does not work, open this link directly:<br>
              <a href="{href}" style="color:#0b5cad;">{escape(url)}</a>
            </p>"""


def render_email_html(
    *,
    logo: str,
    heading: str,
    intro: str,
    note: str,
    code: str | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> str:
    """Render the branded HTML body of an administrator email.

    Pass ``code`` for a large verification-code panel, or ``cta_label`` with
    ``cta_url`` for a primary button plus a copy-paste link fallback.
    """
    body = _code_panel(code) if code else ""
    if cta_label and cta_url:
        body += _cta_panel(cta_label, cta_url)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(heading)}</title>
</head>
<body style="margin:0;padding:0;background-color:#eef2f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#eef2f7;">
    <tr>
      <td align="center" style="padding:28px 12px;">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:560px;background-color:#ffffff;border-radius:16px;border:1px solid #dbe3ee;overflow:hidden;">
          <tr>
            <td style="background-color:{BRAND_ACCENT};background-image:linear-gradient(135deg,#0b5cad 0%,#0e7490 100%);padding:22px 28px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="middle" style="padding-right:14px;">
                    <img src="{escape(logo, quote=True)}" width="46" height="46" alt="{escape(COLLEGE_NAME)}" style="display:block;border-radius:12px;background-color:#ffffff;padding:5px;border:1px solid rgba(255,255,255,0.6);">
                  </td>
                  <td valign="middle">
                    <div style="color:#ffffff;font-size:15px;font-weight:bold;line-height:1.35;">Chalapathi Institute of<br>Engineering &amp; Technology</div>
                    <div style="color:#cfe6ff;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;margin-top:6px;">CIET AI Assistant &middot; Official Notice</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:30px 30px 6px 30px;">
              <div style="font-size:11px;font-weight:bold;letter-spacing:0.16em;text-transform:uppercase;color:#0b5cad;margin-bottom:10px;">Secure message</div>
              <h1 style="margin:0 0 14px 0;font-size:21px;line-height:1.35;color:#0f172a;">{escape(heading)}</h1>
              <p style="margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#334155;">{escape(intro)}</p>{body}
              <p style="margin:20px 0 0 0;font-size:13px;line-height:1.6;color:#64748b;">{escape(note)}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 30px 26px 30px;">
              <div style="border-top:1px solid #e2e8f0;padding-top:16px;font-size:12px;line-height:1.65;color:#94a3b8;">
                &copy; 2026 Chalapathi Institute of Engineering &amp; Technology (CIET) &middot; Sent to a registered administrator address.<br>
                This is an automated security message; please do not reply to it.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
