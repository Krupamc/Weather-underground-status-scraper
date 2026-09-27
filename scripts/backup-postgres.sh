#!/bin/sh
set -eu

# Project root
PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

# Load project environment variables
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR]: Missing environment file: $ENV_FILE"
    exit 1
fi

set -a
. "$ENV_FILE"
set +a


# Docker Compose Postgres settings
DB_SERVICE="db"
DB_NAME=${POSTGRES_DB}
DB_USER=${POSTGRES_USER}

# Backup directory on the VM host
BACKUP_DIR="/opt/mesonet-backups"

TIMESTAMP="$(date '+%Y-%m-%d_%H%M%S')"

echo "[BACKUP]: Creating PostgreSQL backup..."
echo "[BACKUP]: Database: $DB_NAME..."

cd "$PROJECT_DIR"

# Run backup using the existing db_backup container
docker compose exec -T "$BACKUP_SERVICE" /backup.sh


# Find latest backup file
BACKUP_FILE="$(
    find "$BACKUP_DIR" \
        -type f \
        \( -name "*.sql.gz" -o -name "*.dump" -o -name "*.sql" \) \
        -printf "%T@ %p\n" \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
)"


if [ -z "$BACKUP_FILE" ]; then
    echo "[BACKUP ERROR]: No backup archive was found in $BACKUP_DIR"
    exit 1
fi


if [ ! -s "$BACKUP_FILE" ]; then
    echo "[BACKUP ERROR]: Backup file was not created or is empty"
    exit 1
fi


echo "[BACKUP COMPLETE]: $BACKUP_FILE"
echo "[BACKUP COMPLETE]: Size: $(du -h "$BACKUP_FILE" | cut -f1)"

