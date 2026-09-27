#!/bin/sh
set -eu


# Project root
PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"


# Load environment variables
ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "[RESTORE ERROR]: Missing environment file: $ENV_FILE"
    exit 1
fi

set -a
. "$ENV_FILE"
set +a


# Backup directory on host and inside db container
BACKUP_DIR="/opt/mesonet-backups"
CONTAINER_BACKUP_DIR="/backups"


# Docker Compose settings
DB_SERVICE="db"
DB_NAME="${POSTGRES_DB:-mesonet}"
DB_USER="${POSTGRES_USER:-mesonet}"
TEST_DB_NAME="mesonet_restore_test"


echo "[RESTORE TEST]: Finding latest PostgreSQL backup..."


cd "$PROJECT_DIR"


BACKUP_FILE="$BACKUP_DIR/last/mesonet-latest.sql/gz"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR]: Latest backup file not found: $BACKUP_FILE"
    exit 1
fi


if [ ! -s "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR]: Latest backup file is empty: $BACKUP_FILE"
    exit 1
fi

BACKUP_NAME="$(basename "$BACKUP_FILE")"
BACKUP_RELATIVE_PATH="${BACKUP_FILE#$BACKUP_DIR/}"
CONTAINER_BACKUP_FILE="$CONTAINER_BACKUP_DIR/$BACKUP_RELATIVE_PATH"


echo "[RESTORE TEST]: Backup: $BACKUP_FILE"
echo "[RESTORE TEST]: Container backup path: $CONTAINER_BACKUP_FILE"
echo "[RESTORE TEST]: Target database: $TEST_DB_NAME"


# Verify db container can read the selected backup file
if ! docker compose exec -T "$DB_SERVICE" test -f "$CONTAINER_BACKUP_FILE"; then
    echo "[RESTORE ERROR]: Backup file is not visible inside db container"
    echo "[RESTORE ERROR]: Expected: $CONTAINER_BACKUP_FILE"
    echo "[RESTORE ERROR]: Add this db volume mount:"
    echo "[RESTORE ERROR]: - /opt/mesonet-backups:/backups:ro"
    exit 1
fi


# Remove old test database if it exists
docker compose exec -T "$DB_SERVICE" \
    dropdb \
    -U "$DB_USER" \
    --if-exists \
    "$TEST_DB_NAME"


# Create clean temporary test database
docker compose exec -T "$DB_SERVICE" \
    createdb \
    -U "$DB_USER" \
    "$TEST_DB_NAME"


case "$BACKUP_NAME" in
    *.sql.gz)
        echo "[RESTORE TEST]: Restoring compressed SQL backup..."

        docker compose exec -T "$DB_SERVICE" sh -c \
            "gzip -cd '$CONTAINER_BACKUP_FILE' | psql -v ON_ERROR_STOP=1 -U '$DB_USER' -d '$TEST_DB_NAME'"
        ;;

    *.sql)
        echo "[RESTORE TEST]: Restoring SQL backup..."

        docker compose exec -T "$DB_SERVICE" sh -c \
            "psql -v ON_ERROR_STOP=1 -U '$DB_USER' -d '$TEST_DB_NAME' < '$CONTAINER_BACKUP_FILE'"
        ;;

    *.dump)
        echo "[RESTORE TEST]: Restoring PostgreSQL custom archive..."

        docker compose exec -T "$DB_SERVICE" \
            pg_restore \
            -U "$DB_USER" \
            -d "$TEST_DB_NAME" \
            "$CONTAINER_BACKUP_FILE"
        ;;

    *)
        echo "[RESTORE ERROR]: Unsupported backup format: $BACKUP_NAME"
        exit 1
        ;;
esac


echo "[RESTORE TEST]: Checking restored station data..."


docker compose exec -T "$DB_SERVICE" \
    psql \
    -U "$DB_USER" \
    -d "$TEST_DB_NAME" \
    -c "SELECT station_id, station_name FROM station ORDER BY station_name;"


echo "[RESTORE TEST COMPLETE]: Backup restored successfully into $TEST_DB_NAME"