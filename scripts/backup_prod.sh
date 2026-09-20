#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/bri}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET_DIR="${BACKUP_DIR}/${STAMP}"

mkdir -p "$TARGET_DIR"

echo "Writing backups to ${TARGET_DIR}"

docker compose -f "$COMPOSE_FILE" exec -T db sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "${TARGET_DIR}/postgres.dump"

docker compose -f "$COMPOSE_FILE" exec -T backend tar -czf - -C /app media \
  > "${TARGET_DIR}/media.tar.gz"

sha256sum "${TARGET_DIR}/postgres.dump" "${TARGET_DIR}/media.tar.gz" \
  > "${TARGET_DIR}/SHA256SUMS"

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -print -exec rm -rf {} \;

echo "Backup complete:"
ls -lh "$TARGET_DIR"
