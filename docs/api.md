# API Summary

Local interactive OpenAPI is available at `/docs`; production disables docs and the OpenAPI document by default.

- Public health: `GET /healthz`, `GET /readyz`.
- Public widget: `POST /api/v1/chat`, `POST /api/v1/chat/stream`, `POST /api/v1/chat/translate`, `POST /api/v1/feedback`; browser origin policy and an HttpOnly anonymous visitor cookie enforce conversation ownership. The stream endpoint is explicitly **buffered SSE** (`X-CIET-Streaming-Mode: buffered`), not provider-token streaming. `POST /api/v1/chat/translate` re-renders history the client already received when the visitor switches language: it only rewords (never invents), verifies the output landed in the target script, and returns the original line unchanged with `translated: false` when a provider chain fails — but when that failure was a provider rate limit, one bounded recovery pass runs just inside the next quota minute first, because the widget never re-asks for a switch.
- WhatsApp: `GET|POST /api/v1/whatsapp/webhook`; POST requires a valid Meta signature and configured app secret.
- Authentication: `POST /api/v1/auth/login` and `POST /api/v1/auth/otp/request` return a one-time challenge; the emailed six-digit code is redeemed at `POST /api/v1/auth/otp/verify`, which sets the HttpOnly access cookie. Also available: `GET /api/v1/auth/session`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/change-password`, `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`, `POST /api/v1/auth/invitations` (super admin), and `POST /api/v1/auth/accept-invitation`. There is no public signup and no bootstrap endpoint; the first local administrator is provisioned with `python -m scripts.reset_admin`.
- Admin: FAQ, metrics, documents/jobs/reprocessing, knowledge refresh, analytics, conversations, feedback, audit logs, and allowed domains under `/api/v1/admin`.

Admin requests use the HttpOnly cookie and `X-CSRF-Token` for state changes. Bearer authentication is accepted for non-browser clients. All untrusted bodies are Pydantic-validated; upload validation has additional binary checks.
