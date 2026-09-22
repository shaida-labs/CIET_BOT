# Security

## Controls

- Short-lived JWT authentication for the admin API with role-based access control, delivered to browsers in an HttpOnly cookie.
- SameSite/Secure production cookies and double-submit CSRF validation for state-changing admin requests.
- Separate public widget endpoints and protected admin endpoints.
- WhatsApp webhook signature verification with `WHATSAPP_APP_SECRET`.
- Endpoint and application rate limiting through SlowAPI, backed by Redis in non-local environments with an in-memory fallback.
- CORS restricted to `WIDGET_ORIGIN` and `ADMIN_ORIGIN`.
- Trusted host middleware for production host allowlisting.
- No AI answer is allowed to invent official numbers, fees, faculty names, placement percentages, packages, or student counts.
- Admin document uploads are parsed server-side and should be virus-scanned at the platform edge before public deployment.
- Cloudflare R2 credentials and OpenAI credentials are read only from environment variables.
- Widget chat and feedback requests are rejected when the browser origin is outside `ALLOWED_WIDGET_DOMAINS`.
- Document uploads enforce bounded reads, safe filenames, extension-specific MIME/signature checks, Office archive expansion limits, duplicate checksum detection, and ClamAV scanning required by production configuration.
- Admin audit logs track authentication and knowledge-management actions.
- Production startup rejects weak secrets, insecure public origins, missing OpenAI/ClamAV/WhatsApp credentials, wildcard hosts/proxies, and invalid cross-subdomain CSRF configuration.
- API and Nginx responses set CSP, frame, MIME-sniffing, referrer, permissions, and production HSTS controls; version banners are suppressed (Nginx retains a generic server header).
- Interactive docs, OpenAPI, and Prometheus metrics are disabled by default in production.

## Required Production Hardening

- Set a 64+ character `JWT_SECRET`.
- Restrict `ALLOWED_HOSTS` to the API domains.
- Set `CSRF_COOKIE_DOMAIN` when the API and admin use different subdomains of the same parent domain.
- Restrict widget script usage by tenant and domain in an API gateway or WAF.
- Enable Sentry and expose Prometheus metrics only through authenticated/private monitoring infrastructure.
- Run the Celery ingestion worker and Redis with production monitoring.
- Configure `CLAMAV_HOST` for uploaded document scanning.
- Rotate WhatsApp and R2 tokens every semester or on personnel changes.
- Run database backups daily and test restore monthly.



## Reporting

Report suspected vulnerabilities to the CIET technology owner. Do not disclose sensitive student or institutional data publicly.
