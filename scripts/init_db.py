#!/usr/bin/env python3
"""
Legacy database initialization script.
Recommend using database_migrations.py for proper schema management.
"""

import sys
from pathlib import Path

# Add src directory to path to import database_migrations
sys.path.append(str(Path(__file__).parent.parent / "src"))

from database_migrations import main as run_migrations_main

def initialize_db():
    """Initialize database using the migration system."""
    print("Initializing database using migration system...")
    result = run_migrations_main()
    if result == 0:
        print("Database initialization completed successfully")
    else:
        print("Database initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    initialize_db()
