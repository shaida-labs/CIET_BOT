# Architecture

## Runtime components

- `apps/widget`: embeddable React/TypeScript chat widget with English, Telugu, and Hindi UI.
- `apps/admin`: React/TypeScript content and analytics console.
- `services/api`: FastAPI routes, security middleware, SQLAlchemy models, retrieval, uploads, and integrations.
- PostgreSQL: users, knowledge, documents/chunks/jobs, conversations, feedback, analytics, audit, and WhatsApp delivery state.
- Redis: Celery broker/results, response cache/versioning, rate-limit storage, and ingestion duplicate locks.
- Celery worker: extracts/chunks documents and optionally creates Pinecone embeddings.
- Nginx: serves built admin/widget assets.

## Answer flow

`widget/WhatsApp → request validation → FAQ → verified metric → hybrid PostgreSQL/Pinecone RAG → optional bounded official-site search → grounded OpenAI generation → guardrail → response/citations → analytics`

Sensitive statistics go directly through the verified metric gate and cannot be answered by FAQ, RAG, or website text. Other retrieval fails closed when relevance or AI availability is insufficient. Retrieved document and website text is delimited as context and described as untrusted data in the system prompt.

## Admin security flow

`login → bcrypt verification → HttpOnly access cookie + readable CSRF cookie → HS256/issuer/audience/expiry/session-version validation → database active-user/role check → endpoint`

Logout increments `admin_users.session_version`, invalidating every earlier token for that user.

## Trust boundaries

Browser origins, WhatsApp payloads, upload bytes/names, chat text, retrieved document text, external AI/vector/storage services, Redis, and PostgreSQL are separate trust boundaries. The checked-in system is single-tenant; the tenant header is metadata, not authorization.
