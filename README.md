# CIET AI Assistant

Enterprise-grade multi-channel AI assistant platform for Chalapati Institute of Engineering and Technology.

![Status](https://img.shields.io/badge/status-production--ready-0B5D4D)
![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-1565C0)
![Backend](https://img.shields.io/badge/backend-FastAPI-0B5D4D)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)
![AI](https://img.shields.io/badge/AI-OpenAI%20%2B%20RAG-111827)

CIET AI Assistant is not a replacement for the existing college website. It is an embeddable AI assistant platform that integrates with the existing CIET website through a floating widget and also powers a WhatsApp assistant from the same backend.

## Project Overview

CIET AI Assistant provides accurate, trustworthy, and centralized college information to students, parents, faculty, administrators, and visitors.

The platform combines a website widget, WhatsApp channel, admin dashboard, verified FAQ and metrics engines, document-based retrieval, analytics, and guardrails into one maintainable production system.

## Problem Statement

Colleges receive repeated questions every day about admissions, courses, placements, scholarships, hostel facilities, transport, events, departments, contact details, and official processes.

Without a centralized assistant, users face:

- Repeated manual responses from administrative teams.
- Scattered information across documents, web pages, notices, and departments.
- Inconsistent answers from different sources.
- Limited support outside office hours.
- Poor accessibility for students and parents who prefer WhatsApp or mobile-first support.
- Higher risk of unofficial or outdated information being shared.

## Solution

CIET AI Assistant solves this through a single verified information layer shared across multiple channels.

- **Website Widget:** a premium floating AI assistant embedded into the existing CIET website.
- **WhatsApp Assistant:** a WhatsApp Cloud API channel for mobile-first support.
- **Centralized Knowledge System:** FAQs, metrics, uploaded documents, and structured college knowledge managed from the admin dashboard.
- **Verified Responses:** answer priority, confidence scoring, citations, and safe fallback behavior reduce hallucinations.
- **Operational Visibility:** analytics, feedback, audit logs, and monitoring help administrators maintain quality.

## Core Features

- Website floating AI widget.
- WhatsApp AI assistant.
- Admin dashboard for content, FAQs, metrics, documents, analytics, and logs.
- FAQ engine for direct verified answers.
- Metrics engine for official numbers and structured statistics.
- Hybrid RAG over uploaded institutional documents.
- Confidence engine for response quality classification.
- Hallucination prevention and safe fallback responses.
- Multi-language support for English, Telugu, and Hindi.
- PostgreSQL persistence.
- Pinecone vector search.
- Redis and Celery background ingestion.
- JWT authentication and role-aware admin APIs.
- Prometheus, Grafana, and Sentry-ready monitoring.
- Docker-based local and production deployment.

## System Architecture

```text
Students, Parents, Faculty, Visitors
        |
        v
Website Widget + WhatsApp Assistant
        |
        v
FastAPI Backend
        |
        v
Intent Classification
        |
        v
FAQ Engine + Metrics Engine + Hybrid RAG
        |
        v
Confidence Engine
        |
        v
Hallucination Guardrails
        |
        v
OpenAI Response Generation
        |
        v
Verified Final Answer + Citations + Analytics
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, Framer Motion |
| Widget | Shadow DOM embeddable website widget |
| Admin | React admin dashboard |
| Backend | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| AI | OpenAI Responses API, OpenAI embeddings |
| Database | PostgreSQL |
| Vector Database | Pinecone |
| Queue | Redis, Celery |
| Storage | Cloudflare R2 compatible S3 storage |
| Authentication | JWT |
| Monitoring | Prometheus, Grafana, Sentry |
| Deployment | Docker, Docker Compose, Railway, Vercel, Nginx |

## Project Structure

```text
ciet-ai-assistant/
├── apps/
│   ├── admin/                    # Private admin dashboard
│   │   ├── src/                  # Admin React source
│   │   ├── package.json          # Admin scripts and dependencies
│   │   └── vite.config.ts        # Admin Vite configuration
│   └── widget/                   # Embeddable website AI widget
│       ├── src/                  # Widget React source and embed entry
│       ├── package.json          # Widget scripts and dependencies
│       └── vite.config.ts        # Widget Vite library build
├── services/
│   └── api/                      # FastAPI backend service
│       ├── app/
│       │   ├── api/routes/       # HTTP API routes
│       │   ├── core/             # Security, config, domain policy
│       │   ├── db/               # Database session management
│       │   ├── services/         # AI, retrieval, ingestion, guardrails
│       │   └── workers/          # Celery app and background tasks
│       ├── migrations/           # Alembic database migrations
│       ├── tests/                # Backend test suite
│       ├── requirements.txt      # Python runtime dependencies
│       └── pyproject.toml        # Python tooling configuration
├── deploy/                       # Deployment, Nginx, monitoring config
├── docker-compose.yml            # Local multi-service environment
├── Dockerfile.api                # API container image
├── Dockerfile.web                # Widget and admin static web image
├── package.json                  # Root npm workspace scripts
├── .env.example                  # Environment variable template
├── SECURITY.md                   # Security policy
└── README.md                     # Project documentation
```

## How It Works

1. A user asks a question from the website widget or WhatsApp.
2. The backend receives the request through FastAPI.
3. The assistant detects the intent and language.
4. The FAQ engine checks for an exact or high-confidence verified answer.
5. The metrics engine checks structured official data when the question asks for numbers or statistics.
6. The hybrid RAG system searches uploaded documents and knowledge sources.
7. The confidence engine classifies the answer quality.
8. Guardrails prevent unsupported claims and block unsafe or unverified responses.
9. OpenAI generates the final answer when enough verified context exists.
10. The response is returned with confidence, citations when available, and analytics metadata.

## Answer Priority

The assistant answers in this order:

1. Verified FAQ database.
2. Verified metrics database.
3. Hybrid RAG over institutional documents.
4. Website search adapter.
5. Safe fallback response.

The assistant must not invent placement percentages, fee structures, faculty names, student counts, packages, official statistics, or unverified college information.

## Environment Variables

Create a local `.env` file from `.env.example` before running the application.

Required for local development:

```env
ENVIRONMENT=local
API_BASE_URL=http://localhost:8000
WIDGET_ORIGIN=http://localhost:5173
ADMIN_ORIGIN=http://localhost:5174
ALLOWED_HOSTS=localhost,127.0.0.1
ALLOWED_WIDGET_DOMAINS=localhost,127.0.0.1
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ciet_ai
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
JWT_SECRET=replace-with-a-long-random-local-secret
```

Optional integrations:

```env
OPENAI_API_KEY=
PINECONE_API_KEY=
R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
SENTRY_DSN=
```

## Windows Setup

Use **PowerShell** for all Windows commands.

### Windows Prerequisites

Install these tools first:

- Node.js 22 or newer.
- Python 3.12 or newer.
- Git.
- Docker Desktop.
- PostgreSQL, optional when Docker is used.

After installing Docker Desktop, open Docker Desktop once and wait until it says Docker is running.

### Windows Terminal 1: Clone Repository

Run these commands from the folder where you keep projects.

```powershell
git clone <repository-url>
cd ciet-ai-assistant
```

If your repository folder has a different name, replace `ciet-ai-assistant` with that folder name.

### Windows Terminal 1: Install Frontend Dependencies

Run this from the repository root.

```powershell
npm install
```

### Windows Terminal 1: Create Environment Files

Run this from the repository root.

```powershell
copy .env.example .env
```

Open `.env` and fill in any keys needed for your environment. Local development can start with empty OpenAI, Pinecone, WhatsApp, R2, and Sentry values.

### Windows Terminal 1: Create Python Virtual Environment

Run these commands from the repository root.

```powershell
cd services\api
python -m venv .venv
```

### Windows Terminal 1: Activate Python Environment

Run this from `services\api`.

```powershell
.venv\Scripts\activate
```

Your prompt should now show `(.venv)`.

### Windows Terminal 1: Install Backend Dependencies

Run this from `services\api` after activating the virtual environment.

```powershell
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff
```

### Windows Terminal 1: Run Database Services

Run this from the repository root. If you are still inside `services\api`, first run `cd ..\..`.

```powershell
docker compose up -d postgres redis
```

Check that both services are running:

```powershell
docker compose ps
```

### Windows Terminal 1: Run Database Migrations

Run these commands from the repository root.

```powershell
cd services\api
.venv\Scripts\activate
alembic upgrade head
```

### Windows Terminal 1: Run Backend

Run this from `services\api` with the virtual environment activated.

```powershell
uvicorn app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/healthz
```

### Windows Terminal 2: Run Frontend Widget

Open a new PowerShell terminal.

Run this from the repository root.

```powershell
cd apps\widget
npm run dev
```

Widget preview URL:

```text
http://localhost:5173
```

### Windows Terminal 3: Run Admin Dashboard

Open another PowerShell terminal.

Run this from the repository root.

```powershell
cd apps\admin
npm run dev
```

Admin dashboard URL:

```text
http://localhost:5174
```

### Windows Terminal 4: Run Celery Worker

Open another PowerShell terminal.

Run this from the repository root.

```powershell
cd services\api
.venv\Scripts\activate
celery -A app.workers.celery_app.celery_app worker -Q ingestion --loglevel=info
```

If Celery has issues on native Windows, run the worker from WSL2 or Pop!_OS because Celery workers are more reliable on Linux-based environments.

### Windows Verification Commands

Run frontend checks from the repository root.

```powershell
npm run lint
npm run build
```

Run backend checks from `services\api` with the virtual environment activated.

```powershell
pytest
ruff check
```

## Pop!_OS Setup

Use the default **Terminal** application for all Pop!_OS commands.

Pop!_OS is Ubuntu-based, so these commands also work on most recent Ubuntu installations.

### Pop!_OS Terminal 1: Install System Packages

Run this from any folder.

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip docker.io docker-compose-plugin
```

Start Docker and allow your user to run Docker commands.

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and log back in after running `usermod`. This makes Docker group permissions active.

### Pop!_OS Terminal 1: Install Node.js

Run this from any folder.

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Confirm versions:

```bash
node --version
npm --version
python3 --version
docker --version
```

### Pop!_OS Terminal 1: Clone Repository

Run these commands from the folder where you keep projects.

```bash
git clone <repository-url>
cd ciet-ai-assistant
```

If your repository folder has a different name, replace `ciet-ai-assistant` with that folder name.

### Pop!_OS Terminal 1: Install Frontend Dependencies

Run this from the repository root.

```bash
npm install
```

### Pop!_OS Terminal 1: Create Environment Files

Run this from the repository root.

```bash
cp .env.example .env
```

Open `.env` and fill in any keys needed for your environment. Local development can start with empty OpenAI, Pinecone, WhatsApp, R2, and Sentry values.

### Pop!_OS Terminal 1: Create Python Virtual Environment

Run these commands from the repository root.

```bash
cd services/api
python3 -m venv .venv
```

### Pop!_OS Terminal 1: Activate Python Environment

Run this from `services/api`.

```bash
source .venv/bin/activate
```

Your prompt should now show `(.venv)`.

### Pop!_OS Terminal 1: Install Backend Dependencies

Run this from `services/api` after activating the virtual environment.

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff
```

### Pop!_OS Terminal 1: Start Docker Services

Run this from the repository root. If you are still inside `services/api`, first run `cd ../..`.

```bash
docker compose up -d postgres redis
```

If Docker permissions are not active yet, use this command for the current session:

```bash
sudo docker compose up -d postgres redis
```

Check that both services are running:

```bash
docker compose ps
```

### Pop!_OS Terminal 1: Run Database Migrations

Run these commands from the repository root.

```bash
cd services/api
source .venv/bin/activate
alembic upgrade head
```

### Pop!_OS Terminal 1: Run Backend

Run this from `services/api` with the virtual environment activated.

```bash
uvicorn app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/healthz
```

### Pop!_OS Terminal 2: Run Widget

Open a new Terminal window.

Run this from the repository root.

```bash
cd apps/widget
npm run dev
```

Widget preview URL:

```text
http://localhost:5173
```

### Pop!_OS Terminal 3: Run Admin Dashboard

Open another Terminal window.

Run this from the repository root.

```bash
cd apps/admin
npm run dev
```

Admin dashboard URL:

```text
http://localhost:5174
```

### Pop!_OS Terminal 4: Run Celery Worker

Open another Terminal window.

Run this from the repository root.

```bash
cd services/api
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker -Q ingestion --loglevel=info
```

### Pop!_OS Verification Commands

Run frontend checks from the repository root.

```bash
npm run lint
npm run build
```

Run backend checks from `services/api` with the virtual environment activated.

```bash
pytest
ruff check
```

## Local Development URLs

| Service | URL | Purpose |
| --- | --- | --- |
| API | `http://localhost:8000` | FastAPI backend |
| API Health | `http://localhost:8000/healthz` | Health check |
| API Docs | `http://localhost:8000/docs` | Interactive API documentation |
| Widget | `http://localhost:5173` | Website widget preview |
| Admin | `http://localhost:5174` | Admin dashboard |
| Metrics | `http://localhost:8000/metrics` | Prometheus metrics |

## Admin Bootstrap

After the API and database are running, create the first admin user by calling the bootstrap endpoint.

Run from any terminal:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin@ciet.edu","password":"replace-with-a-strong-password"}'
```

On Windows PowerShell, use:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/auth/bootstrap `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"admin@ciet.edu\",\"password\":\"replace-with-a-strong-password\"}"
```

Use a strong password and store it securely.

## Website Widget Integration

Build the widget for production:

```bash
npm run build -w @ciet/widget
```

Embed the generated widget script into the existing CIET website:

```html
<script>
  window.CIET_AI_CONFIG = {
    apiUrl: "https://api.example.edu",
    tenant: "ciet",
    position: "bottom-right",
    privacyUrl: "https://example.edu/privacy"
  };
</script>
<script src="https://cdn.example.edu/widget/ciet-ai.js" defer></script>
```

The widget is designed to mount inside a Shadow DOM boundary so it does not conflict with the existing college website CSS.

## WhatsApp Integration

The WhatsApp assistant uses the same FastAPI backend and knowledge system.

Configure these variables in production:

```env
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

Webhook path:

```text
/api/v1/whatsapp/webhook
```

Use HTTPS in production because WhatsApp Cloud API requires a publicly reachable secure webhook URL.

## Docker Development

Run the full local stack:

```bash
docker compose up --build
```

Services:

| Service | Purpose |
| --- | --- |
| `postgres` | PostgreSQL database |
| `redis` | Redis broker and cache |
| `api` | FastAPI backend |
| `worker` | Celery ingestion worker |
| `web` | Nginx static hosting for widget and admin builds |

## Deployment

Production deployment should use separate managed services for reliability.

Recommended production layout:

- API on Railway, Render, Fly.io, AWS, Azure, or another container platform.
- PostgreSQL as a managed database.
- Redis as a managed cache and Celery broker.
- Widget and admin dashboard on Vercel, Netlify, Cloudflare Pages, or Nginx.
- Pinecone for vector search.
- Cloudflare R2 or compatible S3 storage for uploaded documents.
- Sentry for error reporting.
- Prometheus and Grafana for operational monitoring.

Production requirements:

- Set `ENVIRONMENT=production`.
- Replace `JWT_SECRET` with a long random secret.
- Set production `ALLOWED_HOSTS`.
- Set production `ALLOWED_WIDGET_DOMAINS`.
- Use HTTPS-only public URLs.
- Run `alembic upgrade head` before serving traffic.
- Do not commit `.env` files or secrets.

## Quality Commands

Frontend:

```bash
npm run lint
npm run build
npm run test --workspaces --if-present
```

Backend:

```bash
cd services/api
source .venv/bin/activate
pytest
ruff check
python -m compileall app tests
```

Use the Windows virtual environment activation command on Windows:

```powershell
cd services\api
.venv\Scripts\activate
pytest
ruff check
python -m compileall app tests
```

## Security Notes

- Never commit `.env`, API keys, database passwords, JWT secrets, or WhatsApp tokens.
- Use a strong `JWT_SECRET` in every deployed environment.
- Restrict widget origins with `ALLOWED_WIDGET_DOMAINS`.
- Keep admin access private and role controlled.
- Use HTTPS for all public deployments.
- Review uploaded document handling before enabling public uploads.
- Use the safe fallback behavior when verified information is unavailable.

## Maintenance

Regular maintenance tasks:

- Review unanswered questions and low-confidence responses.
- Update FAQs and metrics when official CIET information changes.
- Re-ingest documents after policy, admission, placement, or fee updates.
- Monitor API latency, error rates, and queue health.
- Rotate secrets periodically.
- Run lint, build, tests, and audit checks before deployment.

## Contributing

Recommended workflow:

1. Create a feature branch.
2. Keep changes scoped to one feature or fix.
3. Run frontend and backend quality commands.
4. Add or update tests when behavior changes.
5. Update documentation for setup, deployment, or operational changes.
6. Open a pull request with a clear summary and verification notes.

## License

This repository is intended for CIET institutional use. Confirm licensing and distribution rules with the project owner before public release.
