#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${2:-}" != "--confirm-data-replacement" ]]; then
  echo "Usage: $0 BACKUP_DIRECTORY --confirm-data-replacement" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BACKUP="$(cd "$1" && pwd)"
[[ -f "$BACKUP/database.dump" && -d "$BACKUP/uploads" ]] || { echo "Backup must contain database.dump and uploads/" >&2; exit 2; }
COMPOSE=(docker compose -f docker-compose.production.yml)
"${COMPOSE[@]}" stop api
restart_api() { "${COMPOSE[@]}" start api >/dev/null || true; }
trap restart_api EXIT
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$BACKUP/database.dump"
"${COMPOSE[@]}" run --rm --no-deps --entrypoint sh api -c 'find /data/uploads -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
"${COMPOSE[@]}" cp "$BACKUP/uploads/." api:/data/uploads/
echo "Restore completed from $BACKUP"
