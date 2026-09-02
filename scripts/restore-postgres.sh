#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: RESTORE_CONFIRM=DATABASE_NAME $0 BACKUP_FILE DATABASE_NAME" >&2
  exit 2
fi

backup_file=$1
database_name=$2
database_user=${POSTGRES_USER:-postgres}

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file does not exist: $backup_file" >&2
  exit 2
fi
if [[ ${RESTORE_CONFIRM:-} != "$database_name" ]]; then
  echo "Refusing restore: set RESTORE_CONFIRM=$database_name" >&2
  exit 2
fi

docker compose exec -T postgres pg_restore \
  --username "$database_user" \
  --dbname "$database_name" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges <"$backup_file"

echo "Restore completed for database $database_name"
