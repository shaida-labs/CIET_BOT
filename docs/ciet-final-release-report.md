# CIET AI Assistant Final Release Report

Date: 2026-08-19 (America/Los_Angeles)  
Release decision: **CONDITIONAL — NOT PRODUCTION READY**

This report closes the locally actionable release blockers without redesigning CIET or adding unrelated product functionality. `PASS` means the stated workflow was executed with the evidence shown. `NOT VERIFIED` is retained wherever credentials, a human acceptance step, or the target production environment was unavailable.

## 1. Current Git Revision

**PASS**

- Revision inspected: `a5f72ddcf60c768ad8bdb37c18e3680f8472790c`.
- Branch: `main` tracking `origin/main`.
- The repository was already dirty from the completed recovery and remained dirty. No reset, clean, or rollback was performed; all existing user changes were preserved.
- Baseline commands executed: `git status --short --branch`, `git log --oneline -10`, and `git diff --stat`.

## 2. Recovery Summary

**PASS**

The recovered application remains the existing CIET architecture: React/TypeScript widget and admin, FastAPI, PostgreSQL, Redis/Celery, optional OpenAI/Pinecone/R2, optional Sentry/ClamAV, and Meta WhatsApp integration. This pass changed only verified release blockers: function-specific RBAC, Python dependency reproducibility, browser accessibility, and release-test evidence.

## 3. CIET Features Verified

| Item | Result | Evidence |
| --- | --- | --- |
| Floating Shadow DOM widget | PASS | Production `ciet-ai.js` mounted and completed a real message/citation/close/reopen journey. |
| Admin | PASS | Live login, analytics, FAQ, metric, document, reprocess, and logs workflows. |
| FAQ | PASS | Live create, exact retrieval with source, and delete. |
| Verified metrics | PASS | Live create/query/delete with verifier and source. |
| Placement safety | PASS | Missing → `92%` verified → deleted → safe fallback; never `0%`. |
| Local ingestion/RAG pipeline | PASS | TXT upload and Celery indexing/reprocess passed; extraction/chunk tests cover PDF, DOCX, XLSX, CSV, TXT, and Markdown. |
| Generated RAG answer | NOT VERIFIED | OpenAI credentials were unavailable. |
| Deterministic multilingual safety | PASS | English, Telugu, Hindi, Roman Telugu, and Roman Hindi regression coverage. |
| Real multilingual model quality | NOT VERIFIED | OpenAI credentials were unavailable. |
| WhatsApp delivery | NOT VERIFIED | Meta sending/signing credentials were unavailable. |

## 4. Accidental AARAV Changes Removed

**PASS**

The prior recovery found no AARAV routes, models, migrations, services, screens, dependencies, or runtime features. Incorrect product-oriented readiness documentation was removed/replaced while generic hardening was preserved. A final source review found no AARAV functionality added by this closure pass.

## 5. OpenAI Result

**NOT VERIFIED — OPENAI CREDENTIALS UNAVAILABLE**

The running API reported `OPENAI_API_KEY=False` and `/readyz` correctly reported AI as degraded. No mock was represented as a live OpenAI result. Therefore the required normal question, document-grounded generation, citations produced through the model, and five-language quality evaluation remain unverified.

## 6. Pinecone Result

**NOT VERIFIED — PINECONE CREDENTIALS UNAVAILABLE**

The runtime had the default index name but `PINECONE_API_KEY=False`. No claim is made for real embeddings, upsert/search, duplicate/orphan/stale-vector checks, reprocessing cleanup, or delete cleanup in Pinecone. PostgreSQL/local ingestion and reprocess passed, but they are not substitutes for the requested live Pinecone lifecycle.

## 7. Cloudflare R2 Result

**NOT VERIFIED — R2 CREDENTIALS UNAVAILABLE**

`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` were absent. Real R2 upload/download/read/delete/reprocess, restart persistence, prefix isolation, and object recovery were not executed. Local volume-backed document persistence does not establish R2 readiness.

## 8. WhatsApp Result

**NOT VERIFIED — META CREDENTIALS UNAVAILABLE**

The default verification token was present, but the app secret, access token, and phone-number ID were absent. Unit/integration coverage passes for HMAC verification, fail-closed configuration, malformed envelopes, status callbacks, and PostgreSQL idempotency; an actual Meta → webhook → CIET retrieval → WhatsApp response was not executed.

## 9. ClamAV Result

**NOT VERIFIED — CLAMAV DAEMON UNAVAILABLE**

`CLAMAV_HOST=False`. Local upload controls pass for a clean TXT document, maximum-size enforcement, invalid extension/MIME/signature rejection, binary/renamed-executable rejection, archive controls, traversal rejection, and the standard EICAR signature. These controls do not prove connectivity or scanning by a real ClamAV daemon.

## 10. Sentry Result

**NOT VERIFIED — SENTRY CREDENTIALS UNAVAILABLE**

`SENTRY_DSN=False`. Optional initialization exists, but no controlled exception could be traced to a received Sentry event. Event scrubbing, alert delivery, dashboards, and paging remain target-environment acceptance items.

## 11. Security Result

| Item | Result | Evidence |
| --- | --- | --- |
| Authentication/session revocation | PASS | JWT issuer/audience/algorithm/version tests and logout revocation pass. |
| Authorization | PASS | Live 20-check role matrix plus denied mutation attempts. |
| CSRF, CORS, host/origin controls | PASS | Backend tests and live browser preflights pass. |
| Upload/path/archive/EICAR controls | PASS | Backend regression suite passes. |
| SSRF/XSS/SQL injection safeguards | PASS | Same-origin bounded website adapter, React escaping, ORM/query binding, and security tests pass. |
| Security headers | PASS | FastAPI and Nginx headers verified; API server banner suppressed. |
| Tracked/image secret scan | PASS | No recognized secret signatures found; only `.env.example` is tracked; no `.env*` file exists in the final API image. |
| npm advisories | PASS | `npm audit --audit-level=high`: 0 vulnerabilities. |
| Python advisories | PASS | `pip-audit -r requirements.lock`: no known vulnerabilities. |
| Production HTTPS/TLS, WAF, secret manager, target credentials | NOT VERIFIED | No deployed CIET production environment or provider evidence was available. |

The Compose manifest is a local/development manifest: it uses development PostgreSQL credentials and publishes PostgreSQL/Redis ports. It must not be treated as the final production network/security configuration.

## 12. Accessibility Result

**NOT VERIFIED** for complete human accessibility acceptance; the executable checks below pass.

| Item | Result | Evidence |
| --- | --- | --- |
| Automated widget axe audit | PASS | Final focused and full live runs: zero violations. |
| Automated admin axe audit | PASS | Final full live run: zero violations. |
| TAB / SHIFT+TAB / ENTER / ESC | PASS | Real Chromium keyboard events; launcher entry, control traversal, Escape close, and launcher focus return verified. |
| Accessible names/semantics | PASS | Launcher, dialog, close, language, history, input, send, citation text, and feedback controls verified. |
| Focus visibility | PASS | Explicit `:focus-visible` styling added and browser-tested. |
| Contrast | PASS | Axe-found widget animation and admin header contrast failures were fixed and rerun unsuppressed. |
| Mobile usability | PASS | No overflow and panel containment at 375, 414, 768, 1024, and 1440 px. |
| Human screen-reader/manual assistive-technology acceptance | NOT VERIFIED | No human screen-reader session was available. |

## 13. Backup/Restore Result

| Item | Result | Evidence |
| --- | --- | --- |
| PostgreSQL backup/restore | PASS | The completed recovery validated backup and isolated restore using the repository scripts. Database schema did not change in this closure. |
| Redis/Celery recovery | PASS | Previously validated restart/recovery; final worker and Redis health are green. |
| R2/object-storage disaster recovery | NOT VERIFIED | R2 credentials were unavailable; no provider backup/reference/recovery could be exercised. |

## 14. RBAC Result

**PASS**

The broad router-level `content_admin` gate was a real defect and was replaced with explicit least-privilege dependencies:

| Role | Permitted | Denied |
| --- | --- | --- |
| Public | Public chat/widget only | All admin routes and metric mutations |
| Admissions admin | FAQ read/write | Metrics, documents, domains, super-admin operational data |
| Placement admin | Verified metric read/write | FAQs, documents, domains, super-admin operational data |
| Content admin | FAQ and document read/write | Verified metrics, domains, super-admin operational data |
| Super admin | All implemented admin functions | — |

Evidence: 20 live authorization status checks returned the expected 200/401/403 results, including public, admissions-admin, and content-admin denied metric mutations. Unit regression coverage also verifies every role guard. The local fixture users were deleted after validation.

## 15. Performance Result

**PASS** for bounded local smoke capacity; **NOT VERIFIED** for a production SLO.

Final within-rate-limit chat run:

| Requests | Concurrency | Success | p50 | p95 | p99 | Total |
| --- | --- | --- | --- | --- | --- | --- |
| 25 | 25 | 25/25 (100%) | 588.4 ms | 621.6 ms | 623.0 ms | 0.629 s |

The earlier recovery also completed 100-request runs at concurrency 25/50/100. Neither measurement includes live OpenAI/Pinecone latency or production network behavior. Exactly 25 synthetic load conversations and 25 corresponding analytics records were removed after this final run.

## 16. Browser Screenshots

**PASS**

Fresh screenshots from the final live run are stored in `qa_evidence/screenshots/live/`:

- `widget-375.png`, `widget-414.png`, `widget-768.png`, `widget-1024.png`, `widget-1440.png`
- `admin-375.png`, `admin-414.png`, `admin-768.png`, `admin-1024.png`, `admin-1440.png`

The live journey used the production-built Shadow DOM embed with no request interception. It exercised student, parent, prospective-student, faculty, and general-visitor questions; the deterministic FAQ path returned a sourced answer and unavailable model-backed questions failed safely.

## 17. Tests

| Validation | Result | Evidence |
| --- | --- | --- |
| Backend | PASS | 62 passed in 3.54 s. |
| Ruff | PASS | `app`, `tests`, and runtime test scripts clean. |
| Python environment | PASS | `pip check`: no broken requirements. |
| Frontend unit | PASS | 1 Vitest file/test passed. |
| ESLint | PASS | Admin and widget, zero warnings. |
| TypeScript/build | PASS | Admin and widget production builds passed. |
| Bundle sizes | PASS | Admin JS 160.83 KB / 52.27 KB gzip; widget embed 228.72 KB / 73.72 KB gzip. |
| Mocked E2E | PASS | Widget feedback, admin FAQ/feedback, responsive, and accessible-name checks. |
| Live E2E | PASS | Exit 0; live API/PostgreSQL/Redis/Celery, placement lifecycle, FAQ, upload/reprocess, logs, keyboard, axe, and five viewports. |
| Accessibility | PASS | Focused axe output: `violations: []`; full widget/admin axe arrays empty. |
| RBAC | PASS | Live role matrix and mutation-denial harness passed. |
| Docker | PASS | Hash-enforced API build and clean frontend image build passed; Compose config valid. |
| Migrations | PASS | Isolated base → head → base → head; current `0004_session_job_integrity`; validation DB removed. |
| Dependencies | PASS | npm and Python advisory scans clean. |
| Load | PASS | 25/25 chat requests returned 200 within the configured limit. |

## 18. Remaining Risks

| Risk | Result |
| --- | --- |
| External AI/vector/object/messaging/malware/monitoring providers have not been acceptance-tested | NOT VERIFIED |
| Target TLS certificates, redirect behavior, WAF policy, network segmentation, secret rotation, and production credentials | NOT VERIFIED |
| Human screen-reader/assistive-technology acceptance | NOT VERIFIED |
| R2 backup, restore, retention, versioning, and integrity recovery | NOT VERIFIED |
| OpenAI-grounded multilingual consistency and hallucination evaluation | NOT VERIFIED |
| Production load/SLO, provider latency, log shipping, dashboards, and paging | NOT VERIFIED |

Python production dependencies are no longer an open risk: `requirements.lock` contains 84 exact packages and 1,667 SHA-256 artifact hashes, Docker installs with `--require-hashes`, the locked image built successfully, and CI installs/audits the lock.

## 19. Exact Production Blockers

1. **NOT VERIFIED — OpenAI:** supply the production/staging key and execute normal, RAG, citation, confidence, and five-language quality acceptance.
2. **NOT VERIFIED — Pinecone:** supply credentials and execute upsert/search/reprocess/delete plus duplicate/orphan/stale-vector checks.
3. **NOT VERIFIED — Cloudflare R2/object DR:** supply credentials and execute persistence, prefix-isolation, restart, backup/reference, restore, and integrity checks.
4. **NOT VERIFIED — Meta WhatsApp:** supply app secret, access token, phone ID, and reachable callback; execute real inbound/outbound/idempotency/status flows.
5. **NOT VERIFIED — ClamAV:** connect staging uploads to a real daemon and prove clean/EICAR/oversize/MIME/renamed-file behavior end to end.
6. **NOT VERIFIED — Sentry/operations:** prove controlled event receipt, scrubbing, log shipping, dashboards, paging, and ownership.
7. **NOT VERIFIED — Production platform:** validate actual HTTPS/TLS, WAF, secrets manager, database/Redis credentials and network exposure, backups, restore, and rollback.
8. **NOT VERIFIED — Human accessibility acceptance:** complete screen-reader and assistive-technology review with CIET’s acceptance owner.

RBAC and Python hash locking are closed and are no longer production blockers.

## 20. Final Decision

**CONDITIONAL — NOT PRODUCTION READY**

The CIET AI Assistant is a technically sound local release candidate. Its core widget/admin path, safety rules, role isolation, ingestion worker, database/cache stack, reproducible build, security checks, responsive behavior, and automated/keyboard accessibility now pass. Launch approval cannot be issued until the eight exact credentialed, target-infrastructure, operational, and human-accessibility blockers above are actually verified.

No `NOT VERIFIED` item has been converted into a `PASS`.
