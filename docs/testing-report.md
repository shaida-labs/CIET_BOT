# Testing Report

Date: 2026-08-19. Results are command outputs observed in this workspace.

| Check | Result |
| --- | --- |
| Backend Pytest | PASS — 61 tests |
| Ruff | PASS |
| Frontend Vitest | PASS |
| Frontend ESLint/TypeScript/Vite | PASS |
| Mocked browser E2E | PASS |
| Live browser E2E | PASS — actual API/PostgreSQL/Redis/Celery and production Shadow DOM bundle |
| Responsive browser sizes | PASS — 375/414/768/1024/1440 |
| npm audit | PASS — 0 vulnerabilities |
| pip-audit / pip check | PASS — none known / no broken requirements |
| Docker Compose | PASS — five healthy services |
| Alembic replay | PASS — head `0004_session_job_integrity` |
| PostgreSQL backup/restore | PASS |
| Live chat load | PASS — 100/100 at concurrency 25, 50, and 100 |
| Official website search adapter | PASS — three real same-origin WordPress results |

External credential paths and a manual WCAG/screen-reader evaluation remain **NOT VERIFIED**. See [ciet-production-readiness-report.md](ciet-production-readiness-report.md) for exact boundaries and measured latency.
