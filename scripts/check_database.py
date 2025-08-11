#!/usr/bin/env python3
"""
Database health check and status utility.
"""

import json
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))
from database_migrations import get_database_stats, get_schema_version

def main():
    """Check and display database status."""
    print("SAME Alert Database Status")
    print("=" * 30)
    
    try:
        stats = get_database_stats()
        
        if stats["status"] == "no_database":
            print("❌ No database found")
            print("Run 'python init_db.py' to initialize")
            return 1
        
        print(f"✅ Status: {stats['status']}")
        print(f"📊 Schema Version: {stats['schema_version']}")
        print(f"📝 Alert Records: {stats['alert_count']:,}")
        print(f"💾 Database Size: {stats['database_size_mb']:.2f} MB")
        print(f"🗂️  Columns: {len(stats['columns'])}")
        print(f"⚡ Indexes: {len(stats['indexes'])}")
        
        print("\nColumns:")
        for col in stats['columns']:
            print(f"  • {col}")
        
        print("\nIndexes:")
        for idx in stats['indexes']:
            print(f"  • {idx}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return 1

if __name__ == "__main__":
    exit(main())