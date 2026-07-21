#!/bin/bash
FAIL_COUNT_FILE="/tmp/neena_watchdog_fail_count"
LOG_FILE="/var/log/neena-backend-watchdog.log"
HEALTH_URL="${NEENA_HEALTH_URL:-http://127.0.0.1:8080/healthz}"
HEALTH_MAX_TIME="${NEENA_HEALTH_MAX_TIME:-10}"
FAIL_THRESHOLD="${NEENA_WATCHDOG_FAIL_THRESHOLD:-6}"

# Initialize fail count file if not exists
if [ ! -f "$FAIL_COUNT_FILE" ]; then
    echo "0" > "$FAIL_COUNT_FILE"
fi

FAIL_COUNT=$(cat "$FAIL_COUNT_FILE")

echo "$(date -Is) - Checking backend health..." >> "$LOG_FILE"
if curl -fsS --max-time "$HEALTH_MAX_TIME" "$HEALTH_URL" > /dev/null 2>&1; then
    # Success, reset counter
    echo "0" > "$FAIL_COUNT_FILE"
    echo "$(date -Is) - Backend is healthy." >> "$LOG_FILE"
else
    # Failure, increment counter
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "$FAIL_COUNT" > "$FAIL_COUNT_FILE"
    echo "$(date -Is) - Backend check failed! Consecutive failures: $FAIL_COUNT" >> "$LOG_FILE"

    if [ "$FAIL_COUNT" -ge "$FAIL_THRESHOLD" ]; then
        echo "$(date -Is) - ${FAIL_THRESHOLD} consecutive failures reached. Restarting neena-backend container..." >> "$LOG_FILE"
        # Reset counter after restart to avoid loop during container startup
        echo "0" > "$FAIL_COUNT_FILE"

        # Restart the container
        cd /opt/orai-radio-command-center || exit 1
        sudo docker compose -f docker-compose.server.yml restart neena-backend >> "$LOG_FILE" 2>&1
        echo "$(date -Is) - Restart command sent." >> "$LOG_FILE"
    fi
fi
