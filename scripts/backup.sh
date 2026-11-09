#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BACKUP_ROOT="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_ROOT/surface-analyzer-$STAMP"
mkdir -p "$TARGET"
COMPOSE=(docker compose -f docker-compose.production.yml)
"${COMPOSE[@]}" ps >/dev/null
restart_api() { "${COMPOSE[@]}" start api >/dev/null || true; }
trap restart_api EXIT
"${COMPOSE[@]}" stop api
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$TARGET/database.dump"
"${COMPOSE[@]}" cp api:/data/uploads "$TARGET/uploads"
cp .env "$TARGET/.env"
echo "Backup created: $TARGET"
