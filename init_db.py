import sqlite3
from pathlib import Path

DB_PATH = Path("alerts.db")

schema = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT,
    originator TEXT,
    event TEXT,
    fips_codes TEXT,
    regions TEXT,
    duration_minutes INTEGER,
    issued_code TEXT,
    source TEXT,
    raw_message TEXT
);
"""

def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    initialize_db()
