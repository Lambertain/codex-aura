#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER_NAME="${CONTAINER_NAME:-codex-aura-neo4j-1}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d_%H%M%S)"
backup_file="neo4j_${timestamp}.dump"

echo "Creating backup ${backup_file}..."
docker exec "${CONTAINER_NAME}" neo4j-admin database dump neo4j --to-path="/backups/${backup_file}"
echo "Copying backup to host..."
docker cp "${CONTAINER_NAME}:/backups/${backup_file}" "${BACKUP_DIR}/${backup_file}"
echo "Backup created at ${BACKUP_DIR}/${backup_file}"
