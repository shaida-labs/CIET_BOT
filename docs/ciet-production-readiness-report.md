# CIET AI Assistant Production Readiness Report

> Superseded by the focused blocker-closure report at
> [`ciet-final-release-report.md`](ciet-final-release-report.md).

Date: 2026-08-19 (America/Los_Angeles)  
Revision inspected: `a5f72ddcf60c768ad8bdb37c18e3680f8472790c` plus the uncommitted recovery changes in this worktree.

## 1. Executive Summary

The repository is correctly a CIET institutional assistant: React/TypeScript website widget and admin console, FastAPI, PostgreSQL, Redis/Celery, optional Pinecone/R2/OpenAI, and WhatsApp Cloud API integration. A real browser journey now passes against the production-built Shadow DOM bundle and live API, database, cache, and worker.

The decision remains **CONDITIONAL — NOT PRODUCTION READY** because credential-dependent OpenAI, Pinecone, R2, Meta WhatsApp, ClamAV, Sentry, and target-environment operations are not verified. No test result below is promoted beyond its actual scope.

## 2. Accidental AARAV Changes Found

No AARAV routes, models, migrations, services, screens, dependencies, scanner, privacy engine, patch engine, tenancy layer, or RLS policies were found. The accidental work was confined to readiness documentation that evaluated CIET against another product's requirements. Git history and the full current source tree were inspected before recovery.

## 3. AARAV Changes Removed

The incorrect product-oriented readiness report was removed. Security, testing, limitations, README, and report pointers were rewritten to assess only CIET requirements. No CIET source capability or useful hardening was removed.

## 4. CIET Changes Preserved

Preserved controls include secure cookie authentication and revocation, CSRF/RBAC, request and upload limits, origin enforcement, rate limits, webhook signature/idempotency handling, worker locking/retries, Docker hardening, health/readiness, backup/restore scripts, responsive accessibility, multilingual safeguards, FAQ/metric/RAG priority, and CI checks.

## 5. Architecture

`College website / WhatsApp → FastAPI → verified FAQ → verified metric → hybrid PostgreSQL/Pinecone RAG → optional official-site adapter → confidence/safety → response and citations`

PostgreSQL stores knowledge and operational records. Redis backs rate limiting, caching, Celery, and ingestion locks. R2/local storage holds source documents. Nginx serves the widget/admin builds. The admin uses an HttpOnly JWT cookie plus a readable double-submit CSRF cookie.

## 6. Backend

FastAPI schema bounds, safe errors, security middleware, persistence, analytics, feedback, and admin operations are covered by 61 passing tests and clean Ruff output. Unexpected exceptions do not expose raw submitted data.

## 7. Frontend

Admin and widget lint, TypeScript compilation, and Vite production builds pass. The admin supports FAQ and metric field-complete CRUD, documents/reprocessing, conversations, feedback, analytics, and authentication. The embed bundle runtime defect found by live E2E was fixed; the final embed is 228.05 KB / 73.52 KB gzip and admin JavaScript is 160.83 KB / 52.27 KB gzip.

## 8. RAG

Upload and extraction support is verified for PDF, DOCX, XLSX, CSV, TXT, and Markdown in code/tests. Chunking now prefers sentence boundaries and never splits words. The live TXT upload indexed and reprocessed through Celery and PostgreSQL. Actual Pinecone embeddings and OpenAI-generated answers are **NOT VERIFIED** without credentials. Citations use document titles/sections when records exist.

## 9. FAQ

Verified FAQ lookup precedes general RAG for non-sensitive questions. Live browser/API testing created an FAQ, retrieved its exact answer and source through public chat, displayed admin state, and deleted the fixture. Sensitive-statistic questions cannot use FAQ text to bypass the metrics gate.

## 10. Metrics

Metrics require name, value, `verified_by`, source, and sensitivity; unit is optional. The admin exposes all fields. Cross-script token normalization preserves Telugu/Hindi combining marks and supports metric matching across English, Telugu, Hindi, Roman Telugu, and Roman Hindi.

## 11. Placement Safety

The required lifecycle passed in both an automated backend regression and the live stack:

1. No placement-percentage metric → low-confidence helpful fallback, no citation, and no `0%`.
2. Create `placement percentage = 92%`, verified by Placement Office, source Official Placement Report.
3. Query → verified `92%` answer with the official source and verifier citation.
4. Delete metric → safe fallback again, never `0%`.

## 12. Multilingual

English, Telugu, Hindi, Roman Telugu, and Roman Hindi detection and placement-safety tests pass. Widget UI switching is browser-tested. Real OpenAI response quality in all languages is **NOT VERIFIED**.

## 13. WhatsApp

GET challenge behavior, HMAC verification, missing-secret fail-closed behavior, PostgreSQL duplicate claims, status handling, and malformed-envelope validation are tested. A live Meta webhook/send with real credentials is **NOT VERIFIED**.

## 14. Admin

Live authentication, analytics load, FAQ creation/deletion, complete metric entry, document upload/reprocess, and conversation persistence passed. Bootstrap remains local-only; logout invalidates prior sessions by incrementing `session_version`.

## 15. Security

Verified controls include fixed-algorithm issuer/audience JWT validation, inactive-user and session-version checks, HttpOnly/SameSite cookies, CSRF, RBAC, CORS/origin/host checks, bounded bodies, signature-aware uploads, archive-bomb controls, EICAR rejection, path traversal protection, webhook replay prevention, recursive audit redaction, safe validation errors, non-root containers, read-only filesystems, and image secret exclusions. Npm and Python advisory scans were clean on 2026-08-19.

## 16. Database

The Alembic chain contains CIET-only revisions through `0004_session_job_integrity`. Isolated base-to-head, head-to-base, and replay passed on PostgreSQL 16; the live stack reports the same head. PostgreSQL backup and isolated restore also passed. No unrelated tenancy/RLS schema was introduced.

## 17. Redis/Celery

Redis and the worker are healthy. Upload and reprocess tasks completed live. A repeated-task defect caused by reusing async database connections across `asyncio.run()` loops was found in live logs, fixed by disposing the engine within each task loop, regression-tested, and rerun without errors. Duplicate document work is guarded by a Redis lock and one durable job per document.

## 18. Docker

Compose configuration, builds, startup, recreation, health checks, and service logs passed. API/worker run as UID 10001; web runs as UID 101. Application filesystems are read-only. No `.env` is present in the API image. Compose uses development credentials and exposed database/cache ports, so it is not the production deployment manifest.

## 19. Monitoring

Liveness, dependency readiness, Prometheus instrumentation, structured logging, and optional Sentry initialization exist. External Sentry delivery, log shipping, dashboards, paging, and production SLOs are **NOT VERIFIED**.

## 20. Performance

Real `/api/v1/chat` tests used 100 requests per run and the placement-safety/PostgreSQL write path. The local rate limit was raised only for the benchmark and restored afterward.

| Concurrency | Success | p50 | p95 | p99 | Total |
| --- | --- | --- | --- | --- | --- |
| 25 | 100/100 | 1305.3 ms | 1772.6 ms | 1824.8 ms | 5.904 s |
| 50 | 100/100 | 1631.7 ms | 1917.1 ms | 1954.4 ms | 3.763 s |
| 100 | 100/100 | 2347.6 ms | 2918.4 ms | 2947.9 ms | 3.016 s |

This is local capacity evidence, not a production SLO or an OpenAI/Pinecone latency result.

## 21. Accessibility

The final live browser verified TAB, SHIFT+TAB, ENTER, ESC, focus entry/return, accessible names, dialog and landmark semantics, language selection, reduced motion, contrast, and no horizontal overflow at 375, 414, 768, 1024, and 1440 pixels. Widget and admin axe audits report zero violations. Human screen-reader/assistive-technology acceptance remains **NOT VERIFIED**.

## 22. E2E

`npm run test:e2e:live` passed without request interception. It covered real admin auth, CORS, production Shadow DOM mounting, user-message/answer/citation rendering, close/reopen behavior, FAQ retrieval, placement lifecycle, document upload/reprocess, conversation persistence, responsive layouts, and accessible control names. The smaller mocked suite remains useful for deterministic frontend isolation and also passes.

## 23. Screenshots

Live screenshots are stored under `qa_evidence/screenshots/live/` for widget and admin widths 375, 414, 768, 1024, and 1440, plus the desktop admin entry state.

## 24. Test Results

- Backend: 62 passed; Ruff clean; pip check clean.
- Frontend: Vitest passed; ESLint and TypeScript/build passed.
- E2E: mocked suite passed; live full-stack suite passed.
- Dependencies: npm 0 vulnerabilities; pip-audit no known vulnerabilities; production Python dependencies are exact and SHA-256 hash-locked.
- Docker: five healthy services; live logs clean after the worker fix.
- Database/recovery: migration replay and PostgreSQL backup/restore passed.

## 25. External Integrations

OpenAI generation/embeddings, Pinecone, R2, Meta WhatsApp, ClamAV daemon scanning, and Sentry delivery are **NOT VERIFIED**. The website adapter is unit-tested for bounded same-origin behavior and returned three results from the real public CIET WordPress endpoint; target-network availability and generated answers remain **NOT VERIFIED**. The adapter is disabled when no official URL is configured.

## 26. Remaining Risks

- No credentialed external-integration acceptance or multilingual model evaluation.
- No target TLS/WAF/secret-manager/deployment evidence.
- Compose is a local manifest with development database credentials and published data ports.
- No automated conversation retention/deletion policy or object-storage disaster recovery.
- CSP still needs inline styles; Nginx retains a generic server banner.
- Accessibility lacks manual assistive-technology verification.
- Human screen-reader/assistive-technology acceptance is still pending.

## 27. Release Gates

| Gate | Result |
| --- | --- |
| CIET architecture/no unrelated product functionality | PASS |
| Backend/frontend/static/build | PASS |
| FAQ and placement safety | PASS |
| Local RAG ingestion/reprocess | PASS |
| Multilingual deterministic safety | PASS |
| Admin live CRUD/auth/logs | PASS |
| Shadow DOM widget and responsive E2E | PASS |
| Docker/health/Redis/Celery | PASS |
| Migrations and PostgreSQL backup/restore | PASS |
| Dependency/security checks | PASS |
| Real OpenAI/Pinecone/R2/WhatsApp/ClamAV/Sentry | NOT VERIFIED |
| Manual WCAG/target deployment/operations | NOT VERIFIED |
| No unresolved high-risk release dependency | FAIL |

## 28. Final Production Decision

**CONDITIONAL — NOT PRODUCTION READY**

The CIET application is a credible local release candidate, and the college-widget critical path now passes live. Production approval requires credentialed external integration tests, target infrastructure/security validation, manual accessibility acceptance, operational monitoring evidence, and explicit acceptance or remediation of the remaining risks.
