# SAMEasy - SAME alert monitor (headless, no e-ink)
# Runs RTL-SDR → rtl_fm → samedec → same_decoder.py
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV RUNTIME_DIR=/app/runtime

# System deps: RTL-SDR, sox, Python, fonts, SQLite. No SPI/e-ink libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    rtl-sdr \
    sox \
    python3 \
    python3-pil \
    python3-pip \
    python3-venv \
    fonts-dejavu-core \
    fontconfig \
    sqlite3 \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust and samedec (SAME decoder)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable \
    && . /root/.cargo/env && cargo install samedec \
    && rm -rf /root/.cargo/registry /root/.cargo/git

ENV PATH="/root/.cargo/bin:${PATH}"

# App lives in /app
WORKDIR /app

# Alerts API (NWS-like GeoJSON for WX fallback); use venv (PEP 668 / externally-managed)
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir flask
ENV PATH="/app/venv/bin:${PATH}"

# Copy only what's needed for headless run (no e-Paper / Waveshare)
COPY config.json ./
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY src/same_decoder.py src/database_migrations.py src/alerts_api.py ./src/
# Optional: copy icons only if you add a future web UI; not needed for decoder
RUN mkdir -p runtime/logs icons

# DB is created on first run by same_decoder.py when /app/runtime is mounted

# Monitor script for Docker (no aplay, no e-ink)
COPY system/same_monitor_docker.sh /app/system/same_monitor_docker.sh
RUN chmod +x /app/system/same_monitor_docker.sh

# Persist runtime (database, logs, last_message.json) via volume
VOLUME ["/app/runtime"]

# Alerts API port (NWS-like endpoint for WX script fallback)
EXPOSE 5000

# RTL-SDR USB device must be passed at run time (e.g. --device /dev/bus/usb/001/002)
ENTRYPOINT ["/app/system/same_monitor_docker.sh"]
