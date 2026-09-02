# Production Runbook

## Normal checks

- Liveness: `GET /healthz` must return 200.
- Readiness: `GET /readyz` must return 200 and depends on PostgreSQL and Redis.
- Worker: `celery ... inspect ping` must return `pong`.
- Database: `alembic current` must report the expected single head.
- Review error rate, request latency, worker failures/retries, queue depth, scan duration, storage failures, and external AI latency.

## Incident response

1. Remove an unready instance from traffic; do not use liveness as readiness.
2. Correlate API, worker, database, Redis, and external-integration logs without copying tokens or raw secrets.
3. For Redis failure, keep the API out of ready state, restore Redis, verify worker reconnect/ping, and then restore traffic.
4. For PostgreSQL failure, stop write traffic, restore service or fail over, verify Alembic head and consistency, then restore traffic.
5. For suspected credential exposure, revoke/rotate the credential, invalidate admin sessions, inspect audit logs, and redeploy.

## Backup and restore

Create a restricted PostgreSQL custom dump:

`scripts/backup-postgres.sh /secure/path/ciet.dump ciet_ai`

Restore only after creating/selecting the target database and explicitly confirming its name:

`RESTORE_CONFIRM=target_db scripts/restore-postgres.sh /secure/path/ciet.dump target_db`

After restore, run `alembic current`, application smoke tests, row-count/integrity checks, and an admin read-only workflow. Separately back up and restore R2/object storage; that path was not validated here.

## Rollback

Prefer application rollback with forward-compatible schema. Test Alembic downgrade on a staging copy before any production downgrade. Never downgrade a production database without a verified backup and an approved maintenance plan.
