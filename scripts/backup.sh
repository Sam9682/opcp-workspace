#!/bin/bash
# ai-shai-web-interface Backup Script

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ai_haccp_backup_$DATE"

mkdir -p "$BACKUP_DIR"

echo "Creating backup: $BACKUP_FILE"
env HTTPS_PORT=6124 HTTP_PORT=6125 HTTPS_PORT1=6126 HTTP_PORT1=6127 HTTPS_PORT2=6128 HTTP_PORT2=6129 HTTPS_PORT3=6130 HTTP_PORT3=6131 HTTPS_PORT4=6132 HTTP_PORT4=6133 HTTPS_PORT5=6134 HTTP_PORT5=6135 USER_ID=1 docker-compose -p "ai-shai-web-interface-1-6124" -f docker-compose.yml exec -T api cp /app/data/ai_haccp.db /tmp/backup.db
docker cp $(docker-compose -p "-1-6124" -f docker-compose.yml ps -q api):/tmp/backup.db "$BACKUP_FILE.db"

if [[ $? -eq 0 ]]; then
    echo "Backup created successfully: $BACKUP_FILE"
    
    # Keep only last 7 backups
    ls -t "$BACKUP_DIR"/ai_haccp_backup_*.db | tail -n +8 | xargs -r rm
    echo "Old backups cleaned up"
else
    echo "Backup failed!"
    exit 1
fi
