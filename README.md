# CIET AI Assistant

CIET AI Assistant is a multi-channel information assistant for **Chalapathi
Institute of Engineering and Technology (CIET), Guntur**. It provides an
embeddable website widget, a private administration console, and an
integration-ready WhatsApp channel backed by the same verified knowledge base.

> **Current status:** the local Docker stack, website widget, admin console,
> verified FAQs, PostgreSQL, Redis, and background worker run locally. WhatsApp
> Cloud API is implemented but **not configured in this environment**; Meta
> credentials and a public HTTPS webhook are still required before it can send
> or receive real WhatsApp messages. See [WhatsApp](#whatsapp-cloud-api).

## Contents

- [What the application does](#what-the-application-does)
- [Architecture](#architecture)
- [Quick start with Docker](#quick-start-with-docker)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Manage knowledge](#manage-knowledge)
- [WhatsApp Cloud API](#whatsapp-cloud-api)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Production checklist](#production-checklist)

## What the application does

| Area | Capability |
| --- | --- |
| Website support | Shadow-DOM widget that can be embedded without affecting the host site’s CSS. |
| Verified answers | FAQ and metric answers are preferred over generated content and include source citations. |
| Knowledge retrieval | Searches approved documents and, when configured, Pinecone and the approved CIET website. |
| Conversation continuity | Uses a bounded, server-side history only from the same verified browser conversation to resolve follow-up questions. |
| Safe responses | Low-confidence questions receive a safe fallback instead of an invented answer. |
| Languages | English, Telugu, and Hindi user interface and request support. |
| Administration | Role-based dashboard for FAQs, metrics, documents, domains, analytics, feedback, and audit logs. |
| Background work | Redis and Celery process document ingestion and WhatsApp replies outside the request path. |
| Security | HttpOnly visitor ownership cookies, JWT/CSRF-protected administration, signed WhatsApp webhooks, rate limiting, and audit events. |
| Observability | Liveness/readiness endpoints, optional Prometheus metrics, structured logs, and optional Sentry. |

## Architecture

```text
Website widget / WhatsApp Cloud API
                 |
                 v
           FastAPI API
                 |
      +----------+----------+
      |                     |
      v                     v
PostgreSQL              Redis / Celery
FAQs, users,            document and WhatsApp jobs
documents, audit
      |
      v
Verified FAQ -> metrics -> document/RAG retrieval -> grounded model response
      |
      v
Answer, citations, feedback, and analytics
```

### Technology

- **Frontend:** React, TypeScript, Vite; embeddable Shadow-DOM widget and admin dashboard
- **API:** Python 3.12, FastAPI, SQLAlchemy, Alembic
- **Data and jobs:** PostgreSQL, Redis, Celery
- **Optional integrations:** OpenAI, Pinecone, Cloudflare R2/S3-compatible storage, Sentry, Meta WhatsApp Cloud API
- **Deployment:** Docker Compose and Nginx for local/integration use

## Quick start with Docker

### Prerequisites

- Docker Engine/Desktop 24+ with Docker Compose v2
- Ports `8000`, `8080`, `5432`, and `6379` available locally

From the repository root:

```bash
docker compose up -d --build
docker compose ps
```

Wait until `api` is healthy, then open:

| Service | Address |
| --- | --- |
| Website widget preview | <http://localhost:8080/widget> |
| Admin dashboard | <http://localhost:8080/admin> |
| API liveness | <http://localhost:8000/healthz> |
| API dependency readiness | <http://localhost:8000/readyz> |
| API documentation (local only) | <http://localhost:8000/docs> |

View logs while starting or diagnosing an issue:

```bash
docker compose logs -f api worker web
```

Stop the local stack without deleting data:

```bash
docker compose down
```

> `docker compose down -v` removes the local PostgreSQL and uploaded-document
> volumes. Use it only when you intentionally want to reset local data.

## Local development

Docker is the recommended path. For frontend development with hot reload, keep
the API dependencies in Docker and run Vite on the host.

```bash
# Terminal 1: API, database, Redis, and worker
docker compose up -d postgres redis api worker

# Terminal 2: install once, then run the widget preview
npm ci
npm run dev:widget

# Terminal 3: optional admin dashboard with hot reload
npm run dev:admin
```

| Development service | Address |
| --- | --- |
| Widget Vite preview | <http://localhost:5173> |
| Admin Vite dashboard | <http://localhost:5174> |
| Docker API | <http://localhost:8000> |

The widget Vite server proxies `/api` to the local Docker API. This removes the
need for a browser cross-origin request during widget development. Restart
`npm run dev:widget` after changing `apps/widget/vite.config.ts`.

### Run the API outside Docker (optional)

Use this only when PostgreSQL and Redis are already available at the addresses
in your `.env` file.

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another terminal, start the worker:

```bash
cd services/api
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
celery -A app.workers.celery_app.celery_app worker \
  -Q ingestion --loglevel=INFO --concurrency=2 --max-tasks-per-child=50
```

## Configuration

The API reads the repository-level `.env` file (or `CIET_ENV_FILE` if set).
Create one from the template only when you need to override defaults or enable
an external service:

```bash
cp .env.example .env                       # Windows PowerShell: Copy-Item .env.example .env
```

Never commit `.env` or real credentials.

### Core local settings

```env
ENVIRONMENT=local
API_BASE_URL=http://localhost:8000
WIDGET_ORIGIN=http://localhost:5173
ADMIN_ORIGIN=http://localhost:5174
ALLOWED_HOSTS=localhost,127.0.0.1
ALLOWED_WIDGET_DOMAINS=localhost,127.0.0.1
JWT_SECRET=replace-with-a-long-random-local-secret
CONVERSATION_MEMORY_MESSAGES=8
CONVERSATION_MEMORY_CHARACTERS=6000
```

Docker Compose supplies its own internal database and Redis URLs. Do not copy
production database passwords into this file.

### Optional services

| Integration | Required variables | Behaviour when absent |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | Verified FAQ and metric answers continue; unsupported generated answers fail closed. |
| Pinecone | `PINECONE_API_KEY`, `PINECONE_INDEX`, `PINECONE_NAMESPACE` | Document vector retrieval is unavailable; FAQ answers still work. |
| R2/S3 storage | `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Local upload storage is used in local development. |
| Official website search | `OFFICIAL_WEBSITE_URL` | The bounded same-origin website adapter is disabled. |
| Sentry | `SENTRY_DSN` | Errors remain in application logs. |
| WhatsApp | See [WhatsApp](#whatsapp-cloud-api) | Webhook POST rejects requests and outbound replies are not sent. |

## Manage knowledge

The assistant can only give reliable institutional answers when verified content
exists. On a fresh installation, add approved FAQs before expecting detailed
admissions, fee, placement, or policy answers.

1. Open the admin dashboard at <http://localhost:8080/admin>.
2. Create the first local administrator if no account exists:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@example.edu","password":"use-a-strong-password"}'
   ```

   Bootstrap is available only in `ENVIRONMENT=local` and only while no admin
   account exists.
3. Sign in and add verified FAQs, metrics, and official documents.
4. Wait for document jobs to finish before relying on document retrieval.
5. Review low-confidence questions and feedback regularly; update content when
   admissions, fees, policies, or contact details change.

The API intentionally returns a safe fallback when the knowledge base cannot
support a claim. This is expected behaviour, not an AI outage.

## WhatsApp Cloud API

### Current state

The WhatsApp integration is **coded and tested for configuration failures**,
but it is not live in the current environment:

- `WHATSAPP_APP_SECRET` is not configured, so inbound POST webhooks reject
  requests with `503` rather than accepting unsigned content.
- `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are not configured,
  so the application cannot send replies through Meta.
- The configured verification token only supports the Meta GET verification
  handshake; it does not make the channel operational by itself.

The delivery path is designed as:

```text
Meta webhook -> signature verification -> idempotent delivery record
             -> Celery job -> CIET knowledge retrieval -> Meta reply API
```

### Enable the channel

1. Create or select a WhatsApp Business app in Meta for Developers and obtain
   its app secret, permanent/system-user access token, and phone-number ID.
2. Set these secrets in the deployment environment; never place them in source
   control:

   ```env
   WHATSAPP_VERIFY_TOKEN=<random-verify-token>
   WHATSAPP_APP_SECRET=<meta-app-secret>
   WHATSAPP_ACCESS_TOKEN=<meta-system-user-token>
   WHATSAPP_PHONE_NUMBER_ID=<meta-phone-number-id>
   ```

3. Deploy the API at a publicly reachable HTTPS address. Meta cannot call
   `localhost`.
4. In Meta, configure the callback URL:

   ```text
   https://api.example.edu/api/v1/whatsapp/webhook
   ```

   Use the exact `WHATSAPP_VERIFY_TOKEN` during webhook verification.
5. Subscribe to message and delivery-status webhook events, then send a real
   test message. Confirm that the webhook verification, inbound record,
   Celery job, outbound delivery, and Meta delivery status are all recorded.

The POST endpoint requires the `X-Hub-Signature-256` HMAC signature. Invalid
or unsigned messages are rejected; duplicate provider message IDs are ignored.

## Embed the widget

Build the production widget:

```bash
npm run build -w @ciet/widget
```

Host the generated `apps/widget/dist/ciet-ai.js` and configure it on the CIET
website:

```html
<script>
  window.CIET_AI_CONFIG = {
    apiUrl: "https://api.example.edu",
    tenant: "ciet",
    position: "bottom-right",
    privacyUrl: "https://www.example.edu/privacy"
  };
</script>
<script src="https://cdn.example.edu/widget/ciet-ai.js" defer></script>
```

In production, set `ALLOWED_WIDGET_DOMAINS` and the exact HTTPS origins to the
college domains. Do not allow arbitrary websites to call the public widget API.

## Testing

Run from the repository root:

```bash
npm run lint
npm run build
npm run test --workspaces --if-present
./.venv/bin/pytest -q services/api/tests
./.venv/bin/ruff check services/api
```

If you use the API virtual environment inside `services/api`, run the final two
commands from that directory as `pytest -q` and `ruff check .` instead.

## Troubleshooting

| Symptom | Check / fix |
| --- | --- |
| Widget says it cannot reach CIET AI | Run `docker compose ps`; verify `api` is healthy; refresh the browser after a rebuild. |
| Browser reports a CORS error on Vite port 5173 | Stop and restart `npm run dev:widget`. The Vite proxy routes `/api` to the Docker API. |
| Widget returns a safe fallback | Add or update a verified FAQ/document. The assistant does not invent unsupported CIET information. |
| Document is stuck or queued | Check `docker compose logs -f worker api`; verify Redis and the worker are healthy. |
| Vector retrieval fails | Verify Pinecone credentials, index name, region, and embedding dimension. FAQ answers remain available without it. |
| WhatsApp webhook returns 503 | Configure `WHATSAPP_APP_SECRET`; see [WhatsApp](#whatsapp-cloud-api). |
| Admin bootstrap returns 409 | An administrator already exists; sign in or use the approved account-recovery process. |

## Production checklist

The included Compose file is a local/integration environment, not a production
deployment manifest. Before a production launch:

- [ ] Use managed PostgreSQL and Redis with backups and restricted network access.
- [ ] Set `ENVIRONMENT=production` and a unique, high-entropy `JWT_SECRET`.
- [ ] Configure exact HTTPS API, widget, and admin origins; set correct allowed hosts and domains.
- [ ] Configure OpenAI, ClamAV, and all required WhatsApp credentials.
- [ ] Validate Pinecone, object storage, Sentry, and the public HTTPS webhook with real credentials.
- [ ] Provision an initial administrator through the approved process; disable local bootstrap access.
- [ ] Upload and approve current institutional FAQs and documents before public launch.
- [ ] Run migrations, tests, dependency/security checks, load checks, and a backup/restore drill.
- [ ] Monitor API errors, queue depth, failed ingestion jobs, unanswered questions, and WhatsApp delivery status.

See [architecture](docs/architecture.md), the [deployment guide](docs/deployment-guide.md),
the [production runbook](docs/production-runbook.md), and [known limitations](docs/known-limitations.md)
for additional operational detail.

## Security

- Do not commit `.env`, access tokens, database passwords, or private keys.
- Keep the admin dashboard private and assign least-privilege roles.
- Treat FAQ, metric, and document updates as reviewed institutional content.
- Use HTTPS for all public endpoints and rotate integration credentials regularly.
- Preserve the safe fallback behaviour when a source is absent or uncertain.

## License

This repository is intended for CIET institutional use. Confirm licensing and
distribution terms with the project owner before public release.
