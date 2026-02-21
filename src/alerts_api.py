#!/usr/bin/env python3
"""
NWS-like alerts API for SAMEasy.
GET /alerts/active?point=lat,lon returns GeoJSON FeatureCollection of active alerts
for the county containing the point (area-filtered so mesh/WX script only gets local alerts).
"""
import csv
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, request

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DB_PATH = str(RUNTIME_DIR / "alerts.db")
CENTROIDS_PATH = DATA_DIR / "county_centroids.csv"

# Event code -> NWS severity (so WX script severity filter works)
EVENT_SEVERITY = {
    "TOR": "Extreme",
    "SVR": "Severe",
    "FFW": "Severe",
    "FLW": "Severe",
    "WSW": "Severe",
    "TOA": "Severe",
    "SVA": "Severe",
    "FFA": "Severe",
}
DEFAULT_SEVERITY = "Severe"

app = Flask(__name__)

_CENTROIDS: Optional[List[Tuple[str, float, float]]] = None


def load_centroids() -> List[Tuple[str, float, float]]:
    """Load (fips, lat, lon) from county_centroids.csv. Cached."""
    global _CENTROIDS
    if _CENTROIDS is not None:
        return _CENTROIDS
    if not CENTROIDS_PATH.exists():
        _CENTROIDS = []
        return _CENTROIDS
    out: List[Tuple[str, float, float]] = []
    with open(CENTROIDS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                fips = (r.get("fips") or "").strip()
                lat = float((r.get("lat") or "0").replace(",", "."))
                lon = float((r.get("lon") or "0").replace(",", "."))
                if fips:
                    out.append((fips, lat, lon))
            except (ValueError, TypeError):
                continue
    _CENTROIDS = out
    return _CENTROIDS


def point_to_fips(lat: float, lon: float) -> Optional[str]:
    """Return the FIPS code of the county whose centroid is nearest to (lat, lon)."""
    centroids = load_centroids()
    if not centroids:
        return None
    best_fips: Optional[str] = None
    best_d2 = float("inf")
    for fips, clat, clon in centroids:
        # Squared Euclidean (degrees) is fine for nearest; Haversine optional
        d2 = (lat - clat) ** 2 + (lon - clon) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_fips = fips
    return best_fips


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def parse_timestamp_utc(ts: str) -> Optional[datetime]:
    """Parse DB timestamp_utc e.g. 'Feb 21 2025, 12:00 UTC' to datetime (UTC)."""
    if not ts:
        return None
    try:
        return datetime.strptime(ts.strip(), "%b %d %Y, %H:%M UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def end_time_utc(row: sqlite3.Row) -> Optional[datetime]:
    """Effective end time (issued + duration_minutes) in UTC."""
    ts = parse_timestamp_utc(row["timestamp_utc"] or "")
    if ts is None:
        return None
    try:
        dur = int(row["duration_minutes"] or 0)
    except (TypeError, ValueError):
        dur = 0
    return ts + timedelta(minutes=dur)


def to_iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def severity_from_event_code(code: Optional[str]) -> str:
    if not code:
        return DEFAULT_SEVERITY
    return EVENT_SEVERITY.get((code or "").strip().upper(), DEFAULT_SEVERITY)


def row_to_nws_feature(row: sqlite3.Row) -> Dict[str, Any]:
    """Map DB row to NWS-like GeoJSON feature for Alert.from_feature()."""
    ts = parse_timestamp_utc(row["timestamp_utc"] or "")
    end = end_time_utc(row)
    fips_codes = [x.strip() for x in (row["fips_codes"] or "").split(",") if x.strip()]
    event_code = (row["event_code"] or "").strip()
    severity = severity_from_event_code(event_code)
    event = (row["event"] or "Unknown").strip()
    regions = (row["regions"] or "").strip()
    headline = f"{event} - {regions}" if regions else event
    return {
        "type": "Feature",
        "id": f"sameasy-{row['id']}",
        "properties": {
            "event": event,
            "severity": severity,
            "urgency": "Unknown",
            "certainty": "Unknown",
            "headline": headline,
            "areaDesc": regions,
            "description": (row["raw_message"] or headline).strip(),
            "instruction": "",
            "sent": to_iso(ts),
            "effective": to_iso(ts),
            "ends": to_iso(end),
            "expires": to_iso(end),
            "geocode": {
                "UGC": fips_codes,
                "SAME": fips_codes,
            },
        },
    }


@app.route("/alerts/active", methods=["GET"])
def alerts_active():
    """Return GeoJSON FeatureCollection of active alerts for the given point. Requires ?point=lat,lon."""
    point = (request.args.get("point") or "").strip()
    if not point:
        return jsonify({"error": "Missing required parameter: point=lat,lon"}), 400
    parts = point.split(",")
    if len(parts) != 2:
        return jsonify({"error": "Invalid point; use point=lat,lon"}), 400
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except ValueError:
        return jsonify({"error": "Invalid lat or lon"}), 400

    fips = point_to_fips(lat, lon)
    if not fips:
        return jsonify({"type": "FeatureCollection", "features": []}), 200

    now = datetime.now(timezone.utc)
    features: List[Dict[str, Any]] = []

    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT id, timestamp_utc, originator, event, event_code, fips_codes, regions,
                   duration_minutes, issued_code, source, raw_message, created_at
            FROM alerts
            ORDER BY created_at DESC
            """
        )
        for row in cursor.fetchall():
            end = end_time_utc(row)
            if end is None or end <= now:
                continue
            alert_fips = [x.strip() for x in (row["fips_codes"] or "").split(",") if x.strip()]
            if fips not in alert_fips:
                continue
            features.append(row_to_nws_feature(row))

    return jsonify({
        "type": "FeatureCollection",
        "features": features,
    }), 200, {"Content-Type": "application/geo+json; charset=utf-8"}


class _SuppressTLSRequestLogging(logging.Filter):
    """Suppress 400 'Bad request version' logs from browsers probing HTTPS on HTTP port."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "Bad request version" not in record.getMessage()


def main() -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    logging.getLogger("werkzeug").addFilter(_SuppressTLSRequestLogging())
    app.run(host="0.0.0.0", port=5000, threaded=True)


if __name__ == "__main__":
    main()
