#!/bin/sh
set -eu

# Monthly Restore test to make sure that the backups can restore.

# Get Variables
PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LOG_DIR="backups/logs"
LOG_FILE="$LOG_DIR/monthly-restore-test-$(date '+%Y-%m-%d_%H%M%S').log"

# Get env file
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "[RESTORE ERROR]: Missing environment file: $ENV_FILE"
    exit 1
fi
set -a
. "$ENV_FILE"
set +a

# Make and open folders
mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"


echo "[$(date -Iseconds)] [RESTORE TEST]: Starting monthly backup restore test" | tee -a "$LOG_FILE"

# Sucess; log
if ./scripts/test-restore-backup.sh >> "$LOG_FILE" 2>&1; then
    echo "[$(date -Iseconds)] [RESTORE TEST]: Success" | tee -a "$LOG_FILE"
    exit 0
fi

# Error; log and email
echo "[$(date -Iseconds)] [RESTORE TEST ERROR]: Failed" | tee -a "$LOG_FILE"
python "$PROJECT_DIR/scripts/send-alerts.py" "[SQL Alert] Monthly Backup Test Failed" "The monthly PostgreSQL backup test failed. Check: $LOG_FILE for more info ~ $SYSTEM_NAME Mesonet Notification System" || true

# End program
exit 1