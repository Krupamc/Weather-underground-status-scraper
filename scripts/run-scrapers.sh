#!/bin/sh
set -eu

# Get the env variables:
STATUS_INTERVAL="${STATUS_SCRAPER_INTERVAL_SECONDS:-900}"
WEATHER_INTERVAL="${WEATHER_SCRAPER_INTERVAL_SECONDS:-60}"

next_status=0

while true; do
    echo "[$(date -Iseconds)]: {RUN} Weather Scraper..."
    python /app/weather_scraper/scrape.py || echo "[ERROR]: Status Scraper failed with exit code $?"
    

    now=$(date +%s) 

    if [ "$now" -ge "$next_status" ]; then
        echo "[$(date -Iseconds)]: {RUN} Status Scraper..."
        python /app/status_scraper/status.py || echo "[ERROR]: Status Scraper failed with exit code $?"

        next_status=$((now + STATUS_INTERVAL))
    fi

        echo "[$(date -Iseconds)] Sleeping for ${WEATHER_INTERVAL} seconds..."
        sleep "$WEATHER_INTERVAL"
done