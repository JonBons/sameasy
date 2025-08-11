import sqlite3
from pathlib import Path
import argparse
from datetime import datetime

DB_PATH = Path("alerts.db")

def connect_db():
    return sqlite3.connect(DB_PATH)

def fetch_alerts(since=None, event=None, limit=10):
    conn = connect_db()
    cursor = conn.cursor()

    query = """
        SELECT timestamp_utc, originator, event, fips_codes,
               regions, duration_minutes, issued_code, source, raw_message
        FROM alerts
    """
    conditions = []
    params = []

    if event:
        conditions.append("event = ?")
        params.append(event)

    if since:
        try:
            datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format for --since (expected YYYY-MM-DD)")
        conditions.append("timestamp_utc >= ?")
        params.append(since)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp_utc DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows

def print_alerts(rows):
    for row in rows:
        (
            timestamp_utc, originator, event, fips_codes, regions,
            duration_minutes, issued_code, source, raw_message
        ) = row
        print("=" * 60)
        print(f"Time     : {timestamp_utc}")
        print(f"Origin   : {originator}")
        print(f"Event    : {event}")
        print(f"FIPS     : {fips_codes}")
        print(f"Regions  : {regions}")
        print(f"Duration : {duration_minutes} minutes")
        print(f"Issued   : {issued_code}")
        print(f"Source   : {source}")
        print(f"Raw Msg  : {raw_message}")
    if rows:
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="View stored SAME alerts")
    parser.add_argument("--since", help="Filter alerts after YYYY-MM-DD")
    parser.add_argument("--event", help="Filter by event name (e.g. 'Tornado Warning')")
    parser.add_argument("--limit", type=int, default=10, help="Number of alerts to display")
    args = parser.parse_args()

    try:
        rows = fetch_alerts(args.since, args.event, args.limit)
        if not rows:
            print("No alerts found.")
        else:
            print_alerts(rows)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
