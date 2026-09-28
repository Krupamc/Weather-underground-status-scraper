#!/bin/sh
set -eu

# Monthly restore test to make sure backups can be restored.

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LOG_DIR="/backups/logs"
LOG_FILE="$LOG_DIR/monthly-restore-test-$(date '+%Y-%m-%d_%H%M%S').log"
RESTORE_SCRIPT="$PROJECT_DIR/scripts/test-restore.sh"
: "${SYSTEM_NAME:=Mesonet}"

# Log everything to monthly file
mkdir -p "$LOG_DIR"

echo "[$(date -Iseconds)] [RESTORE TEST]: Starting monthly backup restore test" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] [RESTORE TEST]: Project dir: $PROJECT_DIR" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] [RESTORE TEST]: Restore script: $RESTORE_SCRIPT" | tee -a "$LOG_FILE"

if [ ! -f "$RESTORE_SCRIPT" ]; then
    echo "[$(date -Iseconds)] [RESTORE TEST ERROR]: Missing restore script: $RESTORE_SCRIPT" | tee -a "$LOG_FILE"
    exit 1
fi

if /bin/sh "$RESTORE_SCRIPT" >> "$LOG_FILE" 2>&1; then
    echo "[$(date -Iseconds)] [RESTORE TEST]: Success" | tee -a "$LOG_FILE"
    exit 0
fi
# On Error email
echo "[$(date -Iseconds)] [RESTORE TEST ERROR]: Failed" | tee -a "$LOG_FILE"
python "$PROJECT_DIR/scripts/send-alerts.py" "[SQL Alert] Monthly Backup Test Failed" "The monthly PostgreSQL backup test failed. Check: $LOG_FILE for more info ~ $SYSTEM_NAME Mesonet Notification System" || true
exit 1