#!/usr/bin/env python3
"""
Database migration system for SAME alert database.
Handles schema versions and safe migrations.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DB_PATH = str(RUNTIME_DIR / "alerts.db")
CURRENT_SCHEMA_VERSION = 2

# Ensure runtime directory exists
RUNTIME_DIR.mkdir(exist_ok=True)

@contextmanager
def get_db_connection():
    """Database connection context manager."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def get_schema_version() -> int:
    """Get current database schema version."""
    try:
        with get_db_connection() as conn:
            # Check if schema_version table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_version'
            """)
            if not cursor.fetchone():
                return 0  # No version table = version 0
            
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Could not determine schema version: {e}")
        return 0

def set_schema_version(version: int):
    """Set schema version in database."""
    with get_db_connection() as conn:
        # Create schema_version table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)
        
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            (version, f"Schema updated to version {version}")
        )
        conn.commit()

def backup_database() -> Path:
    """Create a backup of the current database."""
    if not Path(DB_PATH).exists():
        return None
    
    backup_path = Path(f"{DB_PATH}.backup")
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    logger.info(f"Database backed up to {backup_path}")
    return backup_path

def migration_v0_to_v1():
    """Initial migration: create alerts table with basic schema."""
    logger.info("Running migration v0 -> v1: Initial table creation")
    
    with get_db_connection() as conn:
        conn.execute("""
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
            )
        """)
        conn.commit()

def migration_v1_to_v2():
    """Migration v1 -> v2: Add missing columns and constraints."""
    logger.info("Running migration v1 -> v2: Adding missing columns and constraints")
    
    with get_db_connection() as conn:
        # Check what columns exist
        cursor = conn.execute("PRAGMA table_info(alerts)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add missing columns
        if 'event_code' not in existing_columns:
            conn.execute("ALTER TABLE alerts ADD COLUMN event_code TEXT")
            logger.info("Added event_code column")
        
        if 'created_at' not in existing_columns:
            conn.execute("ALTER TABLE alerts ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            logger.info("Added created_at column")
        
        # Create indexes for better performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp_utc)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_event_code ON alerts(event_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_originator ON alerts(originator)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at)")
        
        conn.commit()
        logger.info("Added performance indexes")

def validate_schema():
    """Validate that the current schema matches expectations."""
    expected_columns = {
        'id', 'timestamp_utc', 'originator', 'event', 'event_code',
        'fips_codes', 'regions', 'duration_minutes', 'issued_code',
        'source', 'raw_message', 'created_at'
    }
    
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(alerts)")
        actual_columns = {row[1] for row in cursor.fetchall()}
        
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns
        
        if missing_columns:
            logger.error(f"Missing columns: {missing_columns}")
            return False
            
        if extra_columns:
            logger.warning(f"Extra columns (not expected): {extra_columns}")
        
        logger.info("Schema validation passed")
        return True

def run_migrations():
    """Run all necessary database migrations."""
    current_version = get_schema_version()
    logger.info(f"Current schema version: {current_version}")
    logger.info(f"Target schema version: {CURRENT_SCHEMA_VERSION}")
    
    if current_version == CURRENT_SCHEMA_VERSION:
        logger.info("Database schema is up to date")
        return True
    
    if current_version > CURRENT_SCHEMA_VERSION:
        logger.error(f"Database version {current_version} is newer than expected {CURRENT_SCHEMA_VERSION}")
        return False
    
    # Create backup before migrations
    backup_path = backup_database()
    if backup_path:
        logger.info(f"Created backup: {backup_path}")
    
    try:
        # Run migrations in sequence
        migrations = [
            (0, 1, migration_v0_to_v1),
            (1, 2, migration_v1_to_v2),
        ]
        
        for from_version, to_version, migration_func in migrations:
            if current_version == from_version:
                migration_func()
                set_schema_version(to_version)
                current_version = to_version
                logger.info(f"Successfully migrated to version {to_version}")
        
        # Validate final schema
        if validate_schema():
            logger.info("All migrations completed successfully")
            return True
        else:
            logger.error("Schema validation failed after migration")
            return False
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if backup_path and backup_path.exists():
            logger.info(f"Consider restoring from backup: {backup_path}")
        raise

def get_database_stats() -> Dict[str, Any]:
    """Get database statistics and health info."""
    if not Path(DB_PATH).exists():
        return {"status": "no_database"}
    
    with get_db_connection() as conn:
        # Get table info
        cursor = conn.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]
        
        cursor = conn.execute("PRAGMA table_info(alerts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        cursor = conn.execute("PRAGMA index_list(alerts)")
        indexes = [row[1] for row in cursor.fetchall()]
        
        return {
            "status": "healthy",
            "schema_version": get_schema_version(),
            "alert_count": alert_count,
            "columns": columns,
            "indexes": indexes,
            "database_size_mb": Path(DB_PATH).stat().st_size / (1024 * 1024)
        }

def main():
    """Main migration runner."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting database migration check")
    
    try:
        success = run_migrations()
        
        if success:
            stats = get_database_stats()
            logger.info(f"Database stats: {stats}")
            logger.info("Database migration completed successfully")
        else:
            logger.error("Database migration failed")
            return 1
            
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())