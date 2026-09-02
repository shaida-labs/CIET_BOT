#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 OUTPUT_FILE [DATABASE_NAME]" >&2
  exit 2
fi

output_file=$1
database_name=${2:-ciet_ai}
database_user=${POSTGRES_USER:-postgres}

mkdir -p "$(dirname "$output_file")"
umask 077
docker compose exec -T postgres pg_dump \
  --username "$database_user" \
  --dbname "$database_name" \
  --format=custom \
  --no-owner \
  --no-privileges >"$output_file"

echo "Backup written to $output_file"
