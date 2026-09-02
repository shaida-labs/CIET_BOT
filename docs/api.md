# API Summary

Local interactive OpenAPI is available at `/docs`; production disables docs and the OpenAPI document by default.

- Public health: `GET /healthz`, `GET /readyz`.
- Public widget: `POST /api/v1/chat`, `POST /api/v1/chat/stream`, `POST /api/v1/feedback`; browser origin policy and an HttpOnly anonymous visitor cookie enforce conversation ownership. The stream endpoint is explicitly **buffered SSE** (`X-CIET-Streaming-Mode: buffered`), not provider-token streaming.
- WhatsApp: `GET|POST /api/v1/whatsapp/webhook`; POST requires a valid Meta signature and configured app secret.
- Authentication: `POST /api/v1/auth/login`, local-only `POST /api/v1/auth/bootstrap`, authenticated/CSRF-protected `POST /api/v1/auth/logout`.
- Admin: FAQ, metrics, documents/jobs/reprocessing, knowledge refresh, analytics, conversations, feedback, audit logs, and allowed domains under `/api/v1/admin`.

Admin requests use the HttpOnly cookie and `X-CSRF-Token` for state changes. Bearer authentication is accepted for non-browser clients. All untrusted bodies are Pydantic-validated; upload validation has additional binary checks.
