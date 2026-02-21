#!/bin/bash
# Headless SAME monitor for Docker: RTL-SDR → samedec → same_decoder.py
# Also runs the alerts API (port 5000) in background for WX script fallback.
# Includes device pre-check and retry loop for USB drop-outs.

set -e
cd /app

FREQ="${SAMEASY_FREQ:-162.4M}"
GAIN="${SAMEASY_GAIN:-29}"
PPM="${SAMEASY_PPM:--35}"
RETRY_DELAY="${SAMEASY_RETRY_DELAY:-5}"
MAX_RETRIES="${SAMEASY_MAX_RETRIES:-}"

mkdir -p runtime/logs

# Start NWS-like alerts API in background (GET /alerts/active?point=lat,lon)
python3 src/alerts_api.py &
API_PID=$!

# Pre-check: ensure RTL-SDR device is visible before starting (exit so container can restart)
if ! rtl_test -t >/dev/null 2>&1; then
  echo "ERROR: RTL-SDR device not found or not usable (run lsusb on host; check device passthrough). Exiting."
  exit 1
fi

run_pipeline() {
  rtl_fm -f "$FREQ" -M fm -s 176400 -r 22050 -E dc -p "$PPM" -g "$GAIN" -E deemp -F 9 | \
    samedec -r 22050 | \
    python3 src/same_decoder.py 2>&1 | tee -a runtime/logs/same_monitor.log
}

retries=0
while true; do
  run_pipeline && exit 0
  retries=$((retries + 1))
  if [ -n "$MAX_RETRIES" ] && [ "$retries" -ge "$MAX_RETRIES" ]; then
    echo "Max retries ($MAX_RETRIES) reached. Exiting."
    exit 1
  fi
  echo "Pipeline exited (e.g. device dropped). Retrying in ${RETRY_DELAY}s (attempt $((retries + 1)))..."
  sleep "$RETRY_DELAY"
done
