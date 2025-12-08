#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="${CONTAINER_NAME:-codex-aura-neo4j-1}"
BACKUP_FILE="${1:-}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

if [[ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_DIR}/${BACKUP_FILE}"
  exit 1
fi

echo "Copying backup into container..."
docker cp "${BACKUP_DIR}/${BACKUP_FILE}" "${CONTAINER_NAME}:/backups/${BACKUP_FILE}"
echo "Restoring database from ${BACKUP_FILE}..."
docker exec "${CONTAINER_NAME}" neo4j-admin database load neo4j --from-path="/backups/${BACKUP_FILE}" --overwrite-destination
echo "Restore complete."
