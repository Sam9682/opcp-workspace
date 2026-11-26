#!/bin/bash
# opcp-workspace Backup Script (PostgreSQL)

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/opcp-workspace_backup_$DATE.sql.gz"

mkdir -p "$BACKUP_DIR"

# Resolve the PostgreSQL container for this project
DB_CONTAINER=$(env HTTPS_PORT=9424 HTTP_PORT=9425 HTTPS_PORT1=9426 HTTP_PORT1=9427 HTTPS_PORT2=9428 HTTP_PORT2=9429 HTTPS_PORT3=9430 HTTP_PORT3=9431 HTTPS_PORT4=9432 HTTP_PORT4=9433 HTTPS_PORT5=9434 HTTP_PORT5=9435 USER_ID=34 docker-compose -p "opcp-workspace-34-9424" -f docker-compose.yml ps -q postgres 2>/dev/null || env HTTPS_PORT=9424 HTTP_PORT=9425 HTTPS_PORT1=9426 HTTP_PORT1=9427 HTTPS_PORT2=9428 HTTP_PORT2=9429 HTTPS_PORT3=9430 HTTP_PORT3=9431 HTTPS_PORT4=9432 HTTP_PORT4=9433 HTTPS_PORT5=9434 HTTP_PORT5=9435 USER_ID=34 docker-compose -p "opcp-workspace-34-9424" -f docker-compose.yml ps -q db 2>/dev/null)

# Resolve credentials (fall back to .env.prod when available)
DB_NAME="${POSTGRES_DB:-opcp-workspace}"
DB_USER="${POSTGRES_USER:-opcp-workspace}"
if [[ -f .env.prod ]]; then
    source .env.prod 2>/dev/null || true
    DB_NAME="${POSTGRES_DB:-$DB_NAME}"
    DB_USER="${POSTGRES_USER:-$DB_USER}"
fi

echo "Creating backup: $BACKUP_FILE"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

if [[ $? -eq 0 && -s "$BACKUP_FILE" ]]; then
    echo "Backup created successfully: $BACKUP_FILE"

    # Keep only last 7 backups
    ls -t "$BACKUP_DIR"/opcp-workspace_backup_*.sql.gz | tail -n +8 | xargs -r rm
    echo "Old backups cleaned up"
else
    echo "Backup failed!"
    exit 1
fi
