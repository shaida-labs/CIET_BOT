# CIET AI Assistant

An enterprise-grade, multi-channel AI information assistant for **Chalapathi
Institute of Engineering and Technology (CIET), Guntur**. It answers admissions,
fees, placements, labs, and policy questions from the college's own verified
knowledge — through an embeddable website widget and (once Meta credentials are
supplied) WhatsApp — with source citations captured on every answer, strict
fail-closed behaviour, and a role-based administration console.

> **Current status:** the full stack (FastAPI, PostgreSQL, Redis, Celery, nginx,
> widget, admin) runs and is verified locally with real Gemini embeddings and
> generation, Pinecone Hybrid RAG, and real browser test suites. WhatsApp,
> live retrieval of the official site from this network, external mailbox
> receipt, and direct OpenAI calls are **blocked on external configuration
> only** — see [Project status](#project-status). Nothing is mocked anywhere in
> the product code.

## Contents

- [Why this project is special](#why-this-project-is-special)
- [How Hybrid RAG works](#how-hybrid-rag-works)
- [Features](#features)
- [Architecture](#architecture)
- [Run the project from scratch](#run-the-project-from-scratch)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Manage knowledge](#manage-knowledge)
- [Embed the widget on a website](#embed-the-widget-on-a-website)
- [WhatsApp Cloud API](#whatsapp-cloud-api)
- [Testing](#testing)
- [Project status](#project-status)
- [Troubleshooting](#troubleshooting)
- [Production checklist](#production-checklist)
- [Documentation](#documentation)

---

## Why this project is special

A typical college chatbot is a keyword matcher or a thin wrapper around one
language model: it guesses, invents numbers, breaks silently when a vendor has
an outage, and cannot prove where an answer came from. This project was built
the opposite way — as an auditable answering *system* around a knowledge base,
not as a model with a prompt.

| Concern | A typical college chatbot | CIET AI Assistant |
| --- | --- | --- |
| Answers come from | Hard-coded scripts, keyword lists, or a general LLM guessing | The college's own approved FAQs, verified metrics, documents, and website — retrieved, not invented |
| Made-up statistics | Common (fees, placement %) | Impossible by design: sensitive numbers only come from the verified metrics store; everything else fails closed to a safe fallback |
| Proof | None | Source citations captured on every document-grounded answer — returned by the API and stored for auditing |
| Retrieval quality | Single keyword **or** single vector search | **Hybrid RAG**: PostgreSQL relevance + Pinecone semantic vectors merged, filtered, and reranked before generation |
| Vendor lock-in | One model provider, outage = down | OpenAI + Gemini + Groq provider chain with automatic failover; **any one API key runs the whole project** |
| Languages | Usually English only | English, Telugu, and Hindi UI and answers, with bundled Indic fonts |
| Channels | One web widget | Website widget and WhatsApp (real Meta Cloud API) served by one knowledge base |
| Content control | Edit source code to change answers | Role-based admin console: FAQs, metrics, document uploads, domains, analytics, feedback, audit logs |
| Security | Session cookie at best | JWT + CSRF + HttpOnly cookies, signed WhatsApp webhooks, OTP login, rate limits, audit trail, virus-scanned uploads, read-only containers |
| Quality assurance | "Seems to work" | 115 backend tests, lint/type gates, three real-browser suites (live E2E, i18n, axe accessibility), and a live RBAC matrix check |
| Missing credentials | Silent broken features | Fail-closed with an explicit `BLOCKED — EXTERNAL CONFIGURATION REQUIRED` status; the rest of the product keeps working |

### Design principles

1. **Zero false pass.** No mocks, fake APIs, fake SMTP/OTP, fake RAG, or
   hard-coded answers exist in product code. Missing credentials produce an
   explicit blocked state — never a pretend success.
2. **Never invent institutional facts.** Low relevance or missing sources ⇒
   a safe fallback answer, always.
3. **Fail closed, degrade gracefully.** A dead LLM provider fails over to the
   next one; a missing provider disables generation but keeps verified FAQ and
   metric answers working; a missing Pinecone keeps the chatbot alive on
   FAQs/metrics.
4. **Untrusted retrieval.** Retrieved document and website text is delimited
   and labelled as untrusted data in the system prompt — it can inform an
   answer, never issue instructions.

---

## How Hybrid RAG works

Hybrid RAG (Retrieval-Augmented Generation) is the core differentiator: instead
of trusting one retrieval method, the system runs **two complementary
searches, merges the results, gates them on relevance, and only then lets the
language model write** — always with citations.

```text
User question
    │
    ├─(1) FAQ lookup ─────────────── exact verified answer + citations ──► reply
    │      (miss)
    ├─(2) Verified metrics gate ──── sensitive stats (placement %, fees…)
    │      (miss)                    only from the reviewed metrics store
    ├─(3) HYBRID RAG retrieval
    │      ├─ PostgreSQL relevance search  (keyword/field matching)
    │      └─ Pinecone vector search       (semantic meaning)
    │           → merged → scored → minimum-score gate → reranked
    │      (relevance ≥ threshold)
    ├─(4) Grounded generation ────── LLM writes strictly from retrieved
    │      (below threshold)         context, context marked untrusted
    └─(5) Safe fallback ──────────── honest "I don't have that yet" reply
                                          │
                    every RAG answer carries source citations ──► reply
```

Why hybrid beats a single method:

- **Keywords alone** miss paraphrases ("How much do I pay?" ≠ "fee
  structure"); **vectors alone** miss exact identifiers (course codes, phone
  numbers, precise statistics). Running both and merging covers each other's
  blind spots.
- The **minimum-score gate** prevents the classic LLM failure of confidently
  answering from irrelevant snippets — weak evidence yields the safe fallback.
- The **verified-metrics step (2)** runs *before* generation, so sensitive
  numbers are computed from reviewed data, never from model memory.
- **Multi-provider failover** sits underneath: embeddings chain
  OpenAI → Gemini, generation chains OpenAI → Gemini → Groq in
  `LLM_PROVIDER_ORDER`, so one vendor's outage or empty credit does not take
  the assistant down.

---

## Features

| Area | Capability |
| --- | --- |
| Website support | Shadow-DOM widget that embeds without touching the host site's CSS/JS; position, colour, logo, and privacy link configurable. |
| Verified answers | FAQ and metric answers are preferred over generated content; every answer carries its source citations in the API response (stored for auditing), while the chat renders a clean answer-only view. |
| Hybrid retrieval | PostgreSQL relevance + Pinecone semantic vectors merged, gated, and reranked; optional bounded search of the official college website. |
| Safe responses | Low-confidence questions receive a safe fallback instead of an invented answer. |
| Multi-LLM | OpenAI, Gemini, and Groq with automatic failover; **any one key keeps the project fully operational**. |
| Conversation continuity | Bounded, server-side history from the same verified browser conversation resolves follow-up questions. |
| Languages | English, Telugu, and Hindi UI and request support — switching language re-renders the entire conversation, history included — with Noto Indic fonts bundled into the widget. |
| Administration | Role-based dashboard (super admin / admin / viewer) for FAQs, metrics, documents, domains, analytics, feedback, and audit logs. |
| Authentication | Two-step login: password + six-digit single-use OTP emailed through real SMTP; JWT in HttpOnly cookies + CSRF protection; invitations instead of public signup. |
| Background work | Redis + Celery handle document ingestion (extract → chunk → embed → index) and WhatsApp replies outside the request path. |
| Channels | Website widget today; WhatsApp through the real Meta Cloud API (signature-verified webhooks) once credentials are supplied. |
| Security | Rate limiting, body-size limits, upload binary validation + ClamAV scanning (production), signed webhooks, audit events, read-only container filesystems. |
| Accessibility | axe-core zero-violation runs at five viewports, keyboard flow, focus management, ARIA semantics — WCAG 2.0/2.1 AA. |
| Observability | `/healthz` and `/readyz` endpoints, structured logs, optional Prometheus metrics + Grafana dashboard, optional Sentry. |

---

## Architecture

```text
                     ┌───────────────────────────────┐
  College website ──►│  Shadow-DOM widget (en/te/hi) │
  WhatsApp (Meta) ──►│  WhatsApp Cloud API webhook   │
                     └──────────────┬────────────────┘
                                    │ HTTPS
                              ┌─────▼─────┐   nginx (web): static admin/widget
                              │  nginx    │   + same-origin /api relay
                              └─────┬─────┘
                              ┌─────▼─────┐
                              │  FastAPI  │  validation → rate limits →
                              │  (api)    │  FAQ → metrics → hybrid RAG →
                              └──┬───┬──┘   website → LLM chain → guardrail
                    ┌────────────┘   └─────────────┐
             ┌──────▼──────┐              ┌────────▼────────┐
             │ PostgreSQL  │              │      Redis      │
             │ FAQs, users │              │ broker, cache,  │
             │ documents,  │              │ rate limits     │
             │ audit, jobs │              └────────┬────────┘
             └──────▲──────┘                       │
                    │                     ┌────────▼────────┐
             ┌──────┴──────┐              │ Celery worker   │
             │  Pinecone   │              │ extract→chunk→  │
             │  vectors    │              │ embed→index     │
             └─────────────┘              └─────────────────┘

  External providers (chained, fail-safe): OpenAI ⇄ Gemini → Groq
  Optional: official website fetch · SMTP · ClamAV · Sentry · R2/S3
```

### Answer pipeline

`widget/WhatsApp → request validation → FAQ → verified metric → hybrid
PostgreSQL/Pinecone RAG → optional bounded official-site search → grounded
generation through the LLM provider chain → guardrail → answer + citations →
analytics`

Sensitive statistics go directly through the verified-metric gate and cannot be
answered by FAQ, RAG, or website text. Retrieval fails closed when relevance or
AI availability is insufficient.

### Technology

- **Frontend:** React 19, TypeScript, Vite — embeddable Shadow-DOM widget and
  admin dashboard (react-router, recharts, i18next)
- **API:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic settings
- **Data & jobs:** PostgreSQL 16, Redis 7, Celery
- **AI:** OpenAI, Gemini, Groq (OpenAI-compatible interfaces), Pinecone
- **Deployment:** Docker Compose, nginx; production overlay adds ClamAV and
  private networking
- **Testing:** pytest + Ruff (API), Vitest (apps), Playwright + Puppeteer +
  axe-core (browser suites), GitHub Actions CI

### Repository layout

```text
CIET_BOT/
├── apps/
│   ├── widget/               # embeddable chat widget (en/te/hi, Shadow DOM)
│   └── admin/                # administration dashboard (react-router)
├── services/api/             # FastAPI app, Celery tasks, Alembic, pytest
│   ├── app/                  # routes, services (llm, retrieval, security…)
│   ├── scripts/              # reset_admin, local_e2e_admin, live_rbac_check
│   └── tests/                # 115 backend tests
├── e2e/                      # browser suites: mocked, live, i18n, a11y
├── docs/                     # architecture, API, deployment, runbook, limits
├── deploy/                   # nginx configs, optional Prometheus/Grafana
├── scripts/                  # backup/restore PostgreSQL, load test
├── docker-compose.yml        # local / integration stack
├── docker-compose.e2e.yml    # E2E overlay (OTP lands in local mail outbox)
├── docker-compose.prod.yml   # production overlay (ClamAV, private DB ports)
├── Dockerfile.api            # non-root, read-only runtime image
├── Dockerfile.web            # builds both frontends + nginx
└── DEPLOYMENT_AND_INTEGRATION.md  # non-technical launch & website guide
```

---

## Run the project from scratch

**Prerequisites**

- Docker Desktop / Docker Engine 24+ with Compose v2 (no local Python or Node
  needed — both are built inside the images)
- Free local ports: `8000` (API), `8080` (web), `5433` (PostgreSQL),
  `6380` (Redis)
- At least **one** LLM API key (OpenAI, Gemini, or Groq) for AI answers;
  without it the stack still runs in fail-closed mode
- *(Development/tests only)* Node 22.12+ and Python 3.12

**1. Get the code**

```bash
git clone <repository-url> CIET_BOT
cd CIET_BOT
```

**2. Create your configuration file**

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Open `.env` and set **at least one** provider key to enable generation and
embeddings:

```env
GEMINI_API_KEY=your-key-here          # or OPENAI_API_KEY / GROQ_API_KEY
LLM_PROVIDER_ORDER=openai,gemini,groq # optional: failover order
```

Everything else has safe local defaults (Compose supplies the database/Redis
URLs). Never commit `.env`.

**3. Start the stack**

```bash
docker compose up -d --build
docker compose ps
```

Wait until every container reports `healthy` (first build takes a few
minutes). Then open:

| Service | Address |
| --- | --- |
| Widget preview | <http://localhost:8080/widget/> |
| Admin dashboard | <http://localhost:8080/admin/> |
| API liveness | <http://localhost:8000/healthz> |
| API readiness (shows `ai: configured` once a key is set) | <http://localhost:8000/readyz> |
| Interactive API docs (local only) | <http://localhost:8000/docs> |

**4. Verify with a real chat request**

```bash
curl http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Where are the labs?","session_id":"scratch-test","language":"en"}'
```

```powershell
# PowerShell equivalent
Invoke-RestMethod -Uri http://localhost:8080/api/v1/chat -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Where are the labs?","session_id":"scratch-test","language":"en"}'
```

Before knowledge is loaded, expect the honest safe fallback — that is the
fail-closed design working, not an error.

**5. Create the first administrator**

There is deliberately no public signup. Provision the first account with the
local-only CLI (password is typed with hidden input and never logged):

```bash
docker compose exec api python -m scripts.reset_admin --email admin@example.edu
```

Sign in at <http://localhost:8080/admin/>. Every login emails a six-digit OTP:

- With `SMTP_*` set in `.env`, the mail is relayed through that real server.
- With SMTP unset (default locally), the real email bytes are written to
  `services/api/storage/mail-outbox/` — read the newest one with:

  ```bash
  docker compose exec api sh -c 'f=$(ls -t storage/mail-outbox | head -1); cat "storage/mail-outbox/$f"'
  ```

**6. Load knowledge**

In the dashboard: add verified **FAQs**, reviewed **metrics** (placement
percentages, fees — these bypass the LLM entirely), and upload official
**documents** (PDF/DOCX/XLSX/TXT). Watch the document status reach
`indexed` before relying on document answers (extraction, chunking, embedding,
and Pinecone upload run in the background worker).

**7. Everyday commands**

```bash
docker compose logs -f api worker web   # follow logs
docker compose down                      # stop, keep all data
docker compose down -v                   # ⚠ delete database + uploads (reset)
docker compose up -d --force-recreate api worker   # apply .env changes
```

To go live on a real server with HTTPS and the college website, follow
**[DEPLOYMENT_AND_INTEGRATION.md](DEPLOYMENT_AND_INTEGRATION.md)** — written
step-by-step for non-technical readers.

---

## Local development

Docker is the recommended path. For frontend hot reload, keep API dependencies
in Docker and run Vite on the host:

```bash
# Terminal 1: API, database, Redis, worker
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

The widget Vite server proxies `/api` to the Docker API, so widget development
needs no cross-origin setup. Restart `npm run dev:widget` after changing
`apps/widget/vite.config.ts`.

### Run the API outside Docker (optional)

Use only when PostgreSQL and Redis are already reachable at the addresses in
your `.env`:

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

---

## Configuration

The API reads the repository-level `.env` file (or `CIET_ENV_FILE` if set).
Copy `.env.example` → `.env` and change only what you need. **Never commit
`.env` or real credentials.**

### LLM providers — any one key is enough

| Setting | Purpose | Default / notes |
| --- | --- | --- |
| `OPENAI_API_KEY` | Generation + embeddings | Optional |
| `GEMINI_API_KEY` | Generation + embeddings | Optional — default generation model `gemini-3.6-flash`, embeddings `gemini-embedding-001` at 3072 dimensions |
| `GROQ_API_KEY` | Generation only (no embeddings) | Optional — default model `openai/gpt-oss-120b` |
| `LLM_PROVIDER_ORDER` | Failover order | `openai,gemini,groq` — unknown or duplicate names are rejected at startup |
| `OPENAI_MODEL` / `OPENAI_MINI_MODEL` | OpenAI model IDs | See `.env.example` |
| `GEMINI_MODEL` / `GROQ_MODEL` | Provider model IDs | See `.env.example` |
| `EMBEDDING_MODEL` + `EMBEDDING_DIMENSIONS` | Vector size must match the model | `text-embedding-3-large` + `3072` (use `1536` only with `text-embedding-3-small`; mismatched values fail startup validation) |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible gateway | Empty |

Behaviour (all live-tested): generation tries each configured provider in
order and fails over on **any** error — including exhausted credit or network
failures — raising an explicit blocked status only when *every* provider
fails. Embeddings chain OpenAI → Gemini, validate vector length (wrong
dimension skips the provider instead of corrupting the index), and fall back
identically. `/readyz` reports `{"ai":"configured"}` only when at least one
usable key exists.

### Core local settings

```env
ENVIRONMENT=local
API_BASE_URL=http://localhost:8000
WIDGET_ORIGIN=http://localhost:5173
ADMIN_ORIGIN=http://localhost:5174
ALLOWED_HOSTS=localhost,127.0.0.1
ALLOWED_WIDGET_DOMAINS=localhost,127.0.0.1
CORS_ORIGINS_EXTRA=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174
JWT_SECRET=replace-with-a-long-random-local-secret
CONVERSATION_MEMORY_MESSAGES=8
CONVERSATION_MEMORY_CHARACTERS=6000
```

Docker Compose supplies its own internal database and Redis URLs. Do not copy
production database passwords into this file.

### Optional services

| Integration | Required variables | Behaviour when absent |
| --- | --- | --- |
| LLM providers | Any ONE of `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY` | FAQ and metric answers continue; generation/embeddings fail closed with `BLOCKED — EXTERNAL CONFIGURATION REQUIRED`. With several keys, a failing provider fails over automatically. |
| Pinecone | `PINECONE_API_KEY`, `PINECONE_INDEX`, `PINECONE_NAMESPACE` | Document vector retrieval is unavailable; FAQ and metric answers still work. |
| R2/S3 storage | `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | Local upload storage is used in local development. |
| Email (SMTP) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Staging/production fail closed (OTP, invitations, resets cannot send → login returns `503`). In `ENVIRONMENT=local`, real email bytes are written to `services/api/storage/mail-outbox/` instead of being relayed. |
| Official website search | `OFFICIAL_WEBSITE_URL` | The bounded same-origin website adapter is disabled. |
| Sentry | `SENTRY_DSN` | Errors remain in application logs. |
| ClamAV | `CLAMAV_HOST` (provided automatically by `docker-compose.prod.yml`) | Production refuses to start without it; local uploads skip scanning. |
| WhatsApp | See [WhatsApp](#whatsapp-cloud-api) | Inbound POST rejects with `503`; outbound replies are not sent. |
| Prometheus/Grafana | Optional files in `deploy/` | No monitoring stack is started; `/metrics` stays disabled in production unless explicitly enabled. |

### Production settings

`ENVIRONMENT=production` deliberately refuses to boot with weak or missing
configuration: 64+ character `JWT_SECRET`, exact HTTPS origins,
non-localhost `ALLOWED_HOSTS` / `ALLOWED_WIDGET_DOMAINS`, at least one LLM key,
reachable `CLAMAV_HOST`, real SMTP, and complete WhatsApp credentials. The
startup error names the offending line. Use the production overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

It injects ClamAV, un-publishes PostgreSQL/Redis, and binds API/web to
`127.0.0.1` so only your HTTPS proxy is public. Full walkthrough:
[DEPLOYMENT_AND_INTEGRATION.md](DEPLOYMENT_AND_INTEGRATION.md) and
[docs/deployment-guide.md](docs/deployment-guide.md).

---

## Manage knowledge

The assistant can only give reliable institutional answers when verified
content exists. On a fresh installation, add approved FAQs before expecting
detailed admissions, fee, placement, or policy answers.

1. Open the admin dashboard at <http://localhost:8080/admin/>.
2. Create the first local administrator if none exists:

   ```bash
   docker compose exec api python -m scripts.reset_admin --email admin@example.edu
   ```

   The command prompts for the password with hidden input, is restricted to
   `ENVIRONMENT=local`, and never accepts or prints a password on the command
   line. Accounts are created by this command or by an existing super admin's
   invitation — there is no public signup and no bootstrap endpoint.
3. Sign in. Every login emails a six-digit, single-use OTP
   (see [email delivery](#email-delivery-and-otp)).
4. Add verified FAQs, metrics, and official documents.
5. Wait for document jobs to finish (`indexed` status) before relying on
   document retrieval.
6. Review low-confidence questions and feedback regularly; update content when
   admissions, fees, policies, or contact details change.

The API intentionally returns a safe fallback when the knowledge base cannot
support a claim. This is expected behaviour, not an AI outage.

## Email delivery and OTP

Administrator sign-in is always two-step: password, then a six-digit OTP that
is generated with a CSPRNG, stored only as a SHA-256 hash, expires after
`OTP_EXPIRY_MINUTES` (default 5), is single-use, and is rate limited with a
resend cooldown. The code never appears in an API response or a log line.

- **Staging/production:** the OTP is relayed through real SMTP. If SMTP is not
  configured the login returns `503` rather than skipping verification.
- **Local (`ENVIRONMENT=local`):** with `SMTP_*` set the message is relayed
  through that real server; with SMTP unset, the exact email bytes are written
  to `services/api/storage/mail-outbox/<sha256-of-address>.eml` (git-ignored,
  `0600`) so development and CI can read what production would have sent.
  There is no simulated or test-only delivery path.

---

## Embed the widget on a website

The Docker image serves the built widget bundle at
`http://localhost:8080/ciet-ai.js` (in production: your HTTPS domain). Add two
script tags to any page:

```html
<script>
  window.CIET_AI_CONFIG = {
    apiUrl: "https://assistant.example.edu", /* REQUIRED — the bot's own URL */
    tenant: "ciet",
    position: "bottom-right",                /* or "bottom-left" */
    privacyUrl: "https://www.example.edu/privacy" /* optional */
  };
</script>
<script src="https://assistant.example.edu/ciet-ai.js" defer></script>
```

> **`apiUrl` is mandatory.** If omitted, the bundle falls back to
> `http://localhost:8000`, which only works on the developer's own machine.
> You can also pass the same values as `data-api-url`, `data-tenant`,
> `data-position`, `data-logo-url`, and `data-privacy-url` attributes on the
> script tag.

Before the widget is allowed to talk to the API, whitelist the host website:

```env
ALLOWED_WIDGET_DOMAINS=www.example.edu,example.edu
CORS_ORIGINS_EXTRA=https://www.example.edu,https://example.edu
```

(origins are `scheme://host` with no trailing slash — they must match the
browser's address bar exactly), then
`docker compose up -d --force-recreate api worker`.

Pages embedding the widget can also open it programmatically with
`window.CIETAI.open()`. A full, screenshot-friendly integration walkthrough is
in [DEPLOYMENT_AND_INTEGRATION.md](DEPLOYMENT_AND_INTEGRATION.md).

## WhatsApp Cloud API

### Current state

The integration is **implemented and tested for failure modes**; it is not
live in this environment because real Meta credentials and a public HTTPS
webhook endpoint are missing:

- Without `WHATSAPP_APP_SECRET`, inbound POST webhooks reject requests with
  `503` rather than accepting unsigned content.
- Without `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`, the app cannot
  send replies through Meta.
- `WHATSAPP_VERIFY_TOKEN` only supports Meta's GET verification handshake.

The delivery path (no Baileys, no QR codes — real Meta Cloud API only):

```text
Meta webhook → HMAC signature check → idempotent delivery record
             → Celery job → knowledge retrieval → Meta replies API
```

### Enable the channel

1. Create or select a WhatsApp Business app in Meta for Developers; obtain the
   app secret, a permanent system-user access token, and the phone-number ID.
2. Put the secrets in the deployment environment (never in source control):

   ```env
   WHATSAPP_VERIFY_TOKEN=<random-verify-token>
   WHATSAPP_APP_SECRET=<meta-app-secret>
   WHATSAPP_ACCESS_TOKEN=<meta-system-user-token>
   WHATSAPP_PHONE_NUMBER_ID=<meta-phone-number-id>
   ```

3. Deploy at a publicly reachable HTTPS address — Meta cannot call
   `localhost`.
4. In Meta, set the callback URL to
   `https://your-domain/api/v1/whatsapp/webhook` and use the exact
   `WHATSAPP_VERIFY_TOKEN` during verification.
5. Subscribe to message and delivery-status events, then send a real test
   message and confirm the webhook verification, inbound record, Celery job,
   outbound delivery, and Meta delivery status are all recorded.

The POST endpoint requires the `X-Hub-Signature-256` HMAC signature; invalid
or unsigned messages are rejected and duplicate provider message IDs ignored.

---

## Testing

Run from the repository root:

```bash
npm run lint                          # ESLint across both apps
npm run build                         # production builds
npm run test --workspaces --if-present
npm run test:e2e                      # mocked-API browser checks, no stack needed
```

Backend checks (CI runs exactly these from `services/api`):

```bash
cd services/api
python -m venv .venv                  # once
.venv\Scripts\activate                # Windows; source .venv/bin/activate on POSIX
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff==0.16.8
pytest -q
ruff check app tests
alembic upgrade head
```

Live suites require the running stack and the reserved E2E administrator
(login redeems a real OTP from the local mail outbox):

```bash
docker compose up -d --build
docker compose exec api python -m scripts.local_e2e_admin create
npm run test:e2e:live         # real PostgreSQL/Redis/Celery/widget/admin journey
npm run test:e2e:widget-i18n  # English/Telugu/Hindi journeys against the real API
npm run test:a11y:live        # axe accessibility scan of the mounted widget
docker compose exec api python -m scripts.live_rbac_check   # server-side role matrix
docker compose exec api python -m scripts.local_e2e_admin delete   # clean up afterwards
```

If `.env` configures `SMTP_HOST`, bring the stack up with the E2E overlay first
so the OTP lands in the local outbox instead of a real mail server, then
restore the normal configuration afterwards:

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d   # E2E
docker compose up -d                                                    # restore
```

### Current results

| Suite | Result |
| --- | --- |
| Backend `pytest` | **128 passed** (incl. multi-provider chain/failover, fail-closed history translation with rate-limit recovery, and premium email-template tests) |
| Backend `ruff check app tests` | Clean |
| Frontend `lint` / `build` / unit `test` | All green |
| `npm run test:e2e` (mocked) | Passed |
| `npm run test:e2e:live` (real stack) | Passed |
| `npm run test:e2e:widget-i18n` (3 languages × desktop/mobile) | Passed |
| `npm run test:a11y:live` (axe, 5 viewports) | Passed, zero violations |
| `scripts.live_rbac_check` | 20/20 |
| Migration `upgrade → downgrade → upgrade` (CI) | Passed |

---

## Project status

Status vocabulary used throughout the project's QA artefacts:
**VERIFIED / FAILED / BLOCKED — EXTERNAL CONFIGURATION REQUIRED / NOT
IMPLEMENTED / NOT TESTED.** There are **zero FAILED** items.

### VERIFIED (exercised against real services)

- Full Docker stack healthy: FastAPI + PostgreSQL + Redis + Celery + nginx;
  migrations apply cleanly; `/healthz` and `/readyz` report `ai: configured`.
- **Hybrid RAG live:** 14 knowledge documents processed (`indexed`), Pinecone
  at 3072 dimensions / 26 vectors, chat route `rag` with real citations; unknown
  questions still receive the safe fallback.
- **Multi-provider LLM chain live:** embeddings 3072-dim via Gemini after an
  OpenAI failover; generation via `gemini-3.6-flash`; chain order
  `openai → gemini → groq`.
- OTP login, RBAC matrix, audit logs, document ingest pipeline, widget
  embedding, i18n (en/te/hi), accessibility, and all suites listed in
  [Testing](#testing).
- Local SMTP path: real email bytes delivered to the local mail outbox and
  redeemed by the live E2E login.

### BLOCKED — EXTERNAL CONFIGURATION REQUIRED (fail-closed, non-blocking)

| Area | What is missing | Behaviour today |
| --- | --- | --- |
| WhatsApp conversation | Meta app credentials + a public HTTPS webhook | Inbound POST rejects `503`; no messages are faked |
| Official-site retrieval | `chalapathiengg.ac.in` unreachable from this network | Bounded website step returns empty; other routes unaffected |
| External SMTP receipt | No external mailbox in this environment | Local outbox delivers the real message bytes; staging/production `503` without SMTP |
| Direct OpenAI calls | Model access/credit unavailable from this network | Automatic failover to Gemini keeps generation and embeddings fully functional; OpenAI's own path stays NOT TESTED until connectivity clears |

---

## Troubleshooting

| Symptom | Check / fix |
| --- | --- |
| Widget says it cannot reach CIET AI | Run `docker compose ps`; verify `api` is healthy; refresh the browser after a rebuild. |
| Browser reports a CORS error on Vite port 5173 | Stop and restart `npm run dev:widget`. The Vite proxy routes `/api` to the Docker API. |
| Widget returns a safe fallback | Add or update a verified FAQ/document. The assistant does not invent unsupported CIET information. |
| `/readyz` shows AI not configured | No usable LLM key. Set one of `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY`, then `docker compose up -d --force-recreate api worker`. |
| Document is stuck or queued | Check `docker compose logs -f worker api`; verify Redis and the worker are healthy. |
| Vector retrieval fails | Verify Pinecone credentials, index name, and that `EMBEDDING_DIMENSIONS` matches the embedding model. FAQ answers remain available without it. |
| API refuses to start after a config change | `docker compose logs api` prints the exact offending setting (production validation fails closed by design). |
| WhatsApp webhook returns 503 | Configure `WHATSAPP_APP_SECRET`; see [WhatsApp](#whatsapp-cloud-api). |
| Admin login says `BLOCKED — EXTERNAL CONFIGURATION REQUIRED` | Real SMTP is not configured. Set `SMTP_*` in `.env`, or run locally with `SMTP_HOST=` to use the mail outbox. |
| Admin login says invalid credentials but the password is right | No administrator exists yet. Provision one with `docker compose exec api python -m scripts.reset_admin --email <address>`. |
| Widget works locally but not on the real site | `apiUrl` missing from the snippet, or the host domain is missing from `ALLOWED_WIDGET_DOMAINS` / `CORS_ORIGINS_EXTRA`. |

---

## Production checklist

The included Compose file is a local/integration environment; use
`docker-compose.prod.yml` as an overlay for real deployments. Before launch:

- [ ] Use managed PostgreSQL and Redis with backups and restricted network
      access (the production overlay already un-publishes the local ports).
- [ ] Set `ENVIRONMENT=production` and a unique, high-entropy `JWT_SECRET`.
- [ ] Configure exact HTTPS API, widget, and admin origins; correct allowed
      hosts and widget domains.
- [ ] Configure at least one LLM provider, ClamAV (overlay-provided), SMTP,
      and all four WhatsApp values.
- [ ] Provision the initial administrator through the approved account process
      (`scripts.reset_admin` is intentionally disabled outside
      `ENVIRONMENT=local`) and rotate its password after first sign-in.
- [ ] Validate Pinecone, object storage, Sentry, and the public HTTPS webhook
      with real credentials.
- [ ] Upload and approve current institutional FAQs and documents.
- [ ] Run migrations, tests, dependency/security checks, load checks, and a
      backup/restore drill.
- [ ] Monitor API errors, queue depth, failed ingestion jobs, unanswered
      questions, and WhatsApp delivery status.

---

## Documentation

| Document | Audience | Contents |
| --- | --- | --- |
| [DEPLOYMENT_AND_INTEGRATION.md](DEPLOYMENT_AND_INTEGRATION.md) | **Non-technical** | Step-by-step hosting, HTTPS, first admin, and putting the widget on the college website |
| [docs/architecture.md](docs/architecture.md) | Developers | Runtime components, answer flow, trust boundaries |
| [docs/api.md](docs/api.md) | Developers | Endpoint summary, auth model |
| [docs/deployment-guide.md](docs/deployment-guide.md) | Operators | Compose deployment + production prerequisites |
| [docs/production-runbook.md](docs/production-runbook.md) | Operators | Health checks, incidents, backup/restore, rollback |
| [docs/known-limitations.md](docs/known-limitations.md) | Everyone | Honest list of what is not yet credential-tested |
| [SECURITY.md](SECURITY.md) | Security | Threat model and hardening summary |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributors | Required checks before submitting a change |

---

## Security

- Do not commit `.env`, access tokens, database passwords, or private keys.
- Keep the admin dashboard private and assign least-privilege roles.
- Treat FAQ, metric, and document updates as reviewed institutional content.
- Use HTTPS for all public endpoints and rotate integration credentials
  regularly.
- Preserve the safe fallback behaviour when a source is absent or uncertain.

## License

This repository is intended for CIET institutional use. Confirm licensing and
distribution terms with the project owner before public release.
