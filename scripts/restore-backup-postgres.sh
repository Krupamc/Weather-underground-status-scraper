#!/bin/sh
set -eu

# Restores DB using latest backup

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
DB_SERVICE="${DB_SERVICE:-db}"
DB_NAME="${POSTGRES_DB:-mesonet}"
DB_USER="${POSTGRES_USER:-mesonet}"


cd "$PROJECT_DIR"


# Use latest backup first
BACKUP_FILE="$BACKUP_DIR/last/mesonet-latest.sql.gz"


# Fallback to newest retained archive if latest is unavailable
if [ ! -s "$BACKUP_FILE" ]; then
    echo "[RESTORE WARNING]: Latest backup unavailable, finding newest retained backup..."

    BACKUP_FILE="$(
        find "$BACKUP_DIR" \
            -type f \
            \( -name "*.sql.gz" -o -name "*.dump" -o -name "*.sql" \) \
            -printf "%T@ %p\n" \
            | sort -nr \
            | head -n 1 \
            | cut -d' ' -f2-
    )"
fi


if [ -z "${BACKUP_FILE:-}" ] || [ ! -s "$BACKUP_FILE" ]; then
    echo "[RESTORE ERROR]: No valid backup archive found"
    exit 1
fi


BACKUP_NAME="$(basename "$BACKUP_FILE")"
BACKUP_RELATIVE_PATH="${BACKUP_FILE#$BACKUP_DIR/}"
CONTAINER_BACKUP_FILE="$CONTAINER_BACKUP_DIR/$BACKUP_RELATIVE_PATH"


if ! docker compose exec -T "$DB_SERVICE" test -f "$CONTAINER_BACKUP_FILE"; then
    echo "[RESTORE ERROR]: Backup file is not visible inside database container"
    echo "[RESTORE ERROR]: Expected: $CONTAINER_BACKUP_FILE"
    exit 1
fi


echo ""
echo "WARNING: This will completely replace the live database: $DB_NAME"
echo "Backup selected: $BACKUP_FILE"
echo ""
printf "Type RESTORE-LIVE-DATABASE to continue: "
read -r CONFIRM


if [ "$CONFIRM" != "RESTORE-LIVE-DATABASE" ]; then
    echo "[RESTORE]: Cancelled"
    exit 0
fi


echo "[RESTORE]: Stopping web and scraper containers..."

docker compose stop web scraper


restore_success=0


case "$BACKUP_NAME" in
    *.sql.gz)
        echo "[RESTORE]: Disconnecting active database sessions..."

        docker compose exec -T "$DB_SERVICE" \
            psql \
            -U "$DB_USER" \
            -d postgres \
            -c "
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '$DB_NAME'
                  AND pid <> pg_backend_pid();
            "


        echo "[RESTORE]: Dropping old database..."

        docker compose exec -T "$DB_SERVICE" \
            dropdb \
            -U "$DB_USER" \
            --if-exists \
            "$DB_NAME"


        echo "[RESTORE]: Creating empty database..."

        docker compose exec -T "$DB_SERVICE" \
            createdb \
            -U "$DB_USER" \
            "$DB_NAME"


        echo "[RESTORE]: Loading compressed SQL backup..."

        if docker compose exec -T "$DB_SERVICE" sh -c \
            "gzip -cd '$CONTAINER_BACKUP_FILE' | psql -v ON_ERROR_STOP=1 -U '$DB_USER' -d '$DB_NAME'"; then
            restore_success=1
        fi
        ;;

    *.sql)
        echo "[RESTORE]: Plain SQL restore requires clean database handling"

        docker compose exec -T "$DB_SERVICE" \
            psql \
            -U "$DB_USER" \
            -d postgres \
            -c "
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '$DB_NAME'
                  AND pid <> pg_backend_pid();
            "

        docker compose exec -T "$DB_SERVICE" \
            dropdb \
            -U "$DB_USER" \
            --if-exists \
            "$DB_NAME"

        docker compose exec -T "$DB_SERVICE" \
            createdb \
            -U "$DB_USER" \
            "$DB_NAME"

        if docker compose exec -T "$DB_SERVICE" sh -c \
            "psql -v ON_ERROR_STOP=1 -U '$DB_USER' -d '$DB_NAME' < '$CONTAINER_BACKUP_FILE'"; then
            restore_success=1
        fi
        ;;

    *.dump)
        echo "[RESTORE]: Restoring custom PostgreSQL archive..."

        if docker compose exec -T "$DB_SERVICE" \
            pg_restore \
            -U "$DB_USER" \
            --clean \
            --if-exists \
            --exit-on-error \
            -d "$DB_NAME" \
            "$CONTAINER_BACKUP_FILE"; then
            restore_success=1
        fi
        ;;

    *)
        echo "[RESTORE ERROR]: Unsupported backup format: $BACKUP_NAME"
        ;;
esac


echo "[RESTORE]: Starting web and scraper containers..."

docker compose start web scraper


if [ "$restore_success" -ne 1 ]; then
    echo "[RESTORE ERROR]: Restore failed. Web and scraper were restarted."
    exit 1
fi


echo "[RESTORE COMPLETE]: Live database restored from $BACKUP_NAME"