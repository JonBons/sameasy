#!/usr/bin/env python3
"""
Test script for SAME decoder with new database schema.
"""

import os
import sys
from pathlib import Path

# Test message for emergency alert system
TEST_MESSAGE = "ZCZC-EAS-RWT-012057-012081-012101-012103-012115+0030-2780415-WTSP/TV-"

def main():
    """Test the SAME decoder with a sample message."""
    print("🧪 Testing SAME Decoder with new database schema")
    print("=" * 50)
    
    # Set environment variable for single message processing
    os.environ["SAMEDEC_MSG"] = TEST_MESSAGE
    
    try:
        # Import and run the decoder
        from same_decoder import main as decoder_main
        print("Running decoder with test message...")
        decoder_main()
        
        print("\n✅ Decoder test completed successfully!")
        
        # Show the results
        print("\n📊 Checking database status:")
        from check_database import main as check_db_main
        check_db_main()
        
        print("\n📋 Viewing the test alert:")
        from view_alerts import main as view_alerts_main
        sys.argv = ["view_alerts.py", "--limit", "1"]
        view_alerts_main()
        
        return 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())