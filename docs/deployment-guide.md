# Deployment Guide

## Local verified deployment

1. Install Docker 24+ and Compose 2.24+.
2. Copy `.env.example` to `.env` only when integrations are needed; never commit it.
3. Run `docker compose build` and `docker compose up -d`.
4. Confirm every row in `docker compose ps` is healthy.
5. Check `http://localhost:8000/healthz`, `http://localhost:8000/readyz`, and `http://localhost:8080/admin/`.

Compose applies Alembic migrations before starting the API. It is a local/integration manifest and deliberately uses development database credentials and published PostgreSQL/Redis ports.

## Production prerequisites

- Managed PostgreSQL/Redis with TLS, backups, private networking, least-privilege accounts, and alerting.
- TLS termination, strict host/origin allowlists, trusted proxy IPs, WAF/body limits, and a secret manager.
- `ENVIRONMENT=production`; HTTPS API/widget/admin URLs; 64+ random JWT secret; shared CSRF cookie domain where required.
- OpenAI, complete WhatsApp credentials, and reachable ClamAV. Configure Pinecone/R2/Sentry when those features are enabled.
- A dedicated production manifest or platform definition. Do not deploy `docker-compose.yml` unchanged.
- Run database migration and rollback rehearsals on a staging copy, then execute smoke/E2E/integration tests against the deployed stack.

Production configuration intentionally fails closed for weak secrets, HTTP origins, local-only hosts, missing OpenAI/ClamAV/WhatsApp configuration, wildcard hosts, and wildcard trusted proxies.
