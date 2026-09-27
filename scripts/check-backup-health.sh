#!/bin/sh
set -eu

# Checks the age of the backups and if the system is taking backups

# Get Variables
BACKUP_FILE="backups/last/mesonet-latest.sql.gz"
MAX_AGE_SECONDS=93600

# Get env file
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[RESTORE ERROR]: Missing environment file: $ENV_FILE"
    exit 1
fi
set -a
. "$ENV_FILE"
set +a

# Look for Backup file
if [ ! -s "$BACKUP_FILE" ]; then
    echo "[BACKUP HEALTH ERROR]: Latest backup missing or empty: $BACKUP_FILE"
    exit 1
fi

now="$(date +%s)"
modified="$(stat -c %Y "$BACKUP_FILE")"
age="$((now - modified))"

# If the file is older than _, Email
if [ "$age" -gt "$MAX_AGE_SECONDS" ]; then
    echo "[BACKUP HEALTH ERROR]: Latest backup is ${age} seconds old"
    python "$PROJECT_DIR/scripts/send-alerts.py" "[SQL Alert] Daily Backup Test Failed" "The daily PostgreSQL backup test failed. The latest backup is over $age long. Check: backup-health.log for more info ~ $SYSTEM_NAME Mesonet Notification System" || true
    exit 1
fi


echo "[BACKUP HEALTH]: Latest backup is healthy"
echo "[BACKUP HEALTH]: File: $BACKUP_FILE"
echo "[BACKUP HEALTH]: Age: ${age} seconds"
echo "[BACKUP HEALTH]: Size: $(du -h "$BACKUP_FILE" | cut -f1)"