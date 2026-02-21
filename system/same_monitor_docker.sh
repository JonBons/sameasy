#!/bin/bash
# Headless SAME monitor for Docker: RTL-SDR → samedec → same_decoder.py
# Also runs the alerts API (port 5000) in background for WX script fallback.

set -e
cd /app

FREQ="${SAMEASY_FREQ:-162.4M}"
GAIN="${SAMEASY_GAIN:-29}"
PPM="${SAMEASY_PPM:--35}"

mkdir -p runtime/logs

# Start NWS-like alerts API in background (GET /alerts/active?point=lat,lon)
python3 src/alerts_api.py &
API_PID=$!

# Run monitor in foreground (keeps container alive, logs to stdout)
exec rtl_fm -f "$FREQ" -M fm -s 176400 -r 22050 -E dc -p "$PPM" -g "$GAIN" -E deemp -F 9 | \
  samedec -r 22050 | \
  python3 src/same_decoder.py 2>&1 | tee -a runtime/logs/same_monitor.log
