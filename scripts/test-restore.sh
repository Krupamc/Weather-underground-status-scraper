#!/bin/sh
set -eu

# Container Script
# Tests restoring the latest backup into a temporary database

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

BACKUP_FILE="/backups/last/mesonet-latest.sql.gz"

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-mesonet}"
DB_USER="${POSTGRES_USER:-mesonet}"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"
TEST_DB_NAME="${TEST_DB_NAME:-mesonet_restore_test}"

export PGPASSWORD="$DB_PASSWORD"

echo "[RESTORE TEST]: Starting container-native restore test..."
echo "[RESTORE TEST]: Backup file: $BACKUP_FILE"
echo "[RESTORE TEST]: DB host: $DB_HOST:$DB_PORT"
echo "[RESTORE TEST]: Test database: $TEST_DB_NAME"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR]: Latest backup file not found: $BACKUP_FILE"
    exit 1
fi

if [ ! -s "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR]: Latest backup file is empty: $BACKUP_FILE"
    exit 1
fi

if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    echo "[RESTORE ERROR]: PostgreSQL is not ready at $DB_HOST:$DB_PORT"
    exit 1
fi

echo "[RESTORE TEST]: Removing old test database if it exists..."
dropdb \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    --if-exists \
    "$TEST_DB_NAME"

echo "[RESTORE TEST]: Creating clean test database..."
createdb \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    "$TEST_DB_NAME"

echo "[RESTORE TEST]: Restoring compressed SQL backup..."
if ! gzip -cd "$BACKUP_FILE" | psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$TEST_DB_NAME" \
    -v ON_ERROR_STOP=1
then
    echo "[RESTORE ERROR]: Restore failed"
    dropdb \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        --if-exists \
        "$TEST_DB_NAME" || true
    exit 1
fi

echo "[RESTORE TEST]: Verifying restored station data..."
psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$TEST_DB_NAME" \
    -v ON_ERROR_STOP=1 \
    -c "SELECT station_id, station_name FROM station ORDER BY station_name;"

echo "[RESTORE TEST]: Counting restored rows..."
psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$TEST_DB_NAME" \
    -v ON_ERROR_STOP=1 \
    -c "SELECT COUNT(*) AS station_count FROM station;"

echo "[RESTORE TEST]: Cleaning up temporary database..."
dropdb \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    --if-exists \
    "$TEST_DB_NAME"

echo "[RESTORE TEST COMPLETE]: Backup restored successfully and cleanup finished"