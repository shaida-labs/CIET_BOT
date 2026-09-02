# Security Audit Report

Date: 2026-08-19. Scope: the CIET AI Assistant source and local Compose deployment present in this workspace.

## Remediated and verified

- Browser login no longer returns the JWT in JSON; the token remains HttpOnly.
- JWTs bind issuer, audience, expiry, HS256, and a database session version. Logout increments that version and records an audit event.
- Bootstrap is rejected outside local development; inactive users cannot log in.
- Validation errors omit submitted input, and unexpected-error logs record exception type instead of raw exception text.
- Audit metadata recursively redacts password/secret/token/API-key fields.
- Widget origin validation covers chat, streaming chat, and feedback and rejects missing origins in production.
- WhatsApp POST verification fails closed when the app secret is absent. Production configuration requires complete WhatsApp credentials.
- Uploads use bounded reads, safe filenames, extension-specific MIME rules, file signatures, UTF-8 checks, Office archive member/expansion/encryption limits, checksum deduplication, EICAR rejection, and production ClamAV configuration.
- Local storage rejects traversal schemes. Docker context excludes every `.env`, virtual environment, cache, generated upload, and evidence directory; image inspection confirmed no `.env` was present.
- API/worker/web containers run non-root; application roots are read-only.
- Npm and Python advisory scans were clean at the recorded audit time.

## Open findings

1. **High — Integration assurance gap.** Real OpenAI, Pinecone, R2, Meta WhatsApp, ClamAV, and Sentry were not exercised with production credentials.
2. **High — Deployment assurance gap.** Target TLS, WAF, secret manager, log shipping, alerting, and production recovery are not validated.
3. **Medium — Authentication feature gap.** CIET has passwords and short-lived access JWTs, but not MFA or fine-grained session inventory.
4. **Medium — Coarse specialized roles.** Admissions and placement role definitions do not yet have a reviewed endpoint-by-endpoint policy.
5. **Medium — Content security policy.** Static pages currently allow inline styles; eliminate them or introduce a nonce/hash design before a strict CSP claim.
6. **Medium — Dependency reproducibility.** Python direct dependencies are lower-bounded and transitive packages are not hash locked.
7. **Medium — Retention/privacy.** Conversation content and query analytics lack automated retention/deletion policies.
8. **Low — Web banner.** Nginx hides its version but still emits the generic `Server: nginx` header.

## Security test evidence

Backend negative tests cover spoofed/traversing/oversized uploads, EICAR, unconfigured WhatsApp, malformed webhook envelopes, unsafe origins, password redaction, session revocation, secure cookies, weak production config, bootstrap restrictions, low-relevance RAG, and security headers. Unauthenticated admin access returned 401. Dependency audits were clean. Redis and PostgreSQL outage drills returned readiness 503 while liveness remained 200.
