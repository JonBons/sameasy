import sqlite3
from pathlib import Path
import argparse
from datetime import datetime
from contextlib import contextmanager

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DB_PATH = str(RUNTIME_DIR / "alerts.db")

@contextmanager
def get_db_connection():
    """Database connection context manager."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        print(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def fetch_alerts(since=None, event=None, event_code=None, limit=10):
    """Fetch alerts with improved filtering and error handling."""
    with get_db_connection() as conn:
        query = """
            SELECT id, timestamp_utc, originator, event, event_code, fips_codes,
                   regions, duration_minutes, issued_code, source, raw_message, created_at
            FROM alerts
        """
        conditions = []
        params = []

        if event:
            conditions.append("event LIKE ?")
            params.append(f"%{event}%")
        
        if event_code:
            conditions.append("event_code = ?")
            params.append(event_code)

        if since:
            try:
                datetime.strptime(since, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Invalid date format for --since (expected YYYY-MM-DD)")
            conditions.append("DATE(created_at) >= ?")
            params.append(since)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return rows

def print_alerts(rows):
    """Print formatted alert information."""
    for i, row in enumerate(rows):
        print("=" * 70)
        print(f"Alert #{row['id']} ({i+1} of {len(rows)})")
        print("=" * 70)
        print(f"Event      : {row['event']}")
        if row['event_code']:
            print(f"Code       : {row['event_code']}")
        print(f"Originator : {row['originator']}")
        print(f"Source     : {row['source']}")
        print(f"Regions    : {row['regions']}")
        print(f"Duration   : {row['duration_minutes']} minutes")
        print(f"Issued     : {row['timestamp_utc']}")
        print(f"Received   : {row['created_at']}")
        print(f"FIPS Codes : {row['fips_codes']}")
        print(f"Raw Message: {row['raw_message']}")
        print()
    
    if rows:
        print("=" * 70)
        print(f"Total: {len(rows)} alert(s) displayed")

def main():
    parser = argparse.ArgumentParser(
        description="View stored SAME alerts",
        epilog="Examples:\n"
               "  python view_alerts.py --limit 5\n"
               "  python view_alerts.py --event 'Warning' --since 2025-08-01\n"
               "  python view_alerts.py --event-code 'TOR'\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--since", help="Filter alerts after YYYY-MM-DD")
    parser.add_argument("--event", help="Filter by event name (partial match, e.g. 'Warning')")
    parser.add_argument("--event-code", help="Filter by specific event code (e.g. 'TOR', 'FFW')")
    parser.add_argument("--limit", type=int, default=10, help="Number of alerts to display (default: 10)")
    args = parser.parse_args()

    # Check if database exists
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        print("Run 'python init_db.py' to initialize the database.")
        return 1

    try:
        rows = fetch_alerts(args.since, args.event, args.event_code, args.limit)
        if not rows:
            print("📭 No alerts found matching your criteria.")
            print("\nTry adjusting your filters or check if any alerts have been received.")
        else:
            print(f"📡 SAME Alert Database - Showing {len(rows)} alert(s)\n")
            print_alerts(rows)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
