#!/usr/bin/env python3
import csv
import os
import sys
import sqlite3
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone

# Local imports - database_migrations is in same directory
from database_migrations import run_migrations, get_database_stats

# ---------- Project Setup ----------
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DB_PATH = str(RUNTIME_DIR / "alerts.db")
JSON_OUTPUT_PATH = str(RUNTIME_DIR / "last_message.json")

# Ensure runtime directories exist
RUNTIME_DIR.mkdir(exist_ok=True)
(RUNTIME_DIR / "logs").mkdir(exist_ok=True)

# ---------- Setup logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(RUNTIME_DIR / 'logs' / 'same_decoder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global cache for CSV data
_csv_cache: Dict[str, Dict[str, Dict[str, str]]] = {}


@contextmanager
def get_db_connection():
    """Database connection context manager with proper error handling."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def initialize_database():
    """Initialize database with proper migrations."""
    try:
        logger.info("Initializing database with migration system")
        success = run_migrations()
        
        if not success:
            raise RuntimeError("Database migration failed")
        
        # Log database stats
        stats = get_database_stats()
        logger.info(f"Database ready - Version: {stats.get('schema_version')}, Records: {stats.get('alert_count')}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def stream_decode_from_stdin():
    """Stream decode SAME messages from stdin with error handling."""
    initialize_database()
    load_all_csv_data()  # Cache CSV data once
    
    buffer = ""
    logger.info("Starting SAME message stream processing")
    
    try:
        for line in sys.stdin:
            line = line.strip()
            
            # Skip unrelated noise (warnings, empty lines)
            if not line.startswith("ZCZC-"):
                continue
            
            # Handle multiline SAME messages (if they ever break across lines)
            buffer += line
            if line.endswith("-"):
                try:
                    decode_same_message(buffer)
                except Exception as e:
                    logger.error(f"Error decoding message '{buffer}': {e}")
                buffer = ""
    except KeyboardInterrupt:
        logger.info("Stream processing interrupted by user")
    except Exception as e:
        logger.error(f"Error in stream processing: {e}")
        raise

def load_csv_to_dict(filename: str, key_field: str) -> Dict[str, Dict[str, str]]:
    """Load CSV file to dictionary with error handling."""
    path = DATA_DIR / filename
    
    if not path.exists():
        logger.error(f"CSV file not found: {path}")
        raise FileNotFoundError(f"Required CSV file not found: {path}")
    
    try:
        with path.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = {row[key_field]: row for row in reader if key_field in row}
            logger.info(f"Loaded {len(data)} records from {filename}")
            return data
    except Exception as e:
        logger.error(f"Error loading CSV file {filename}: {e}")
        raise

def load_all_csv_data():
    """Load all CSV data into global cache."""
    global _csv_cache
    
    try:
        _csv_cache['originators'] = load_csv_to_dict("originators.csv", "code")
        _csv_cache['events'] = load_csv_to_dict("eas_events.csv", "code")
        _csv_cache['counties'] = load_csv_to_dict("fips_counties.csv", "fips")
        _csv_cache['states'] = load_csv_to_dict("fips_states.csv", "code")
        logger.info("All CSV data loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load CSV data: {e}")
        raise

def validate_same_message_format(msg: str) -> str:
    """Validate and sanitize SAME message format."""
    if not isinstance(msg, str):
        raise ValueError(f"Message must be a string, got {type(msg)}")
    
    msg = msg.strip()
    
    if not msg:
        raise ValueError("Message cannot be empty")
    
    if not msg.startswith("ZCZC-"):
        raise ValueError("Message must start with 'ZCZC-'")
    
    if len(msg) > 1000:  # Reasonable limit for SAME messages
        raise ValueError(f"Message too long: {len(msg)} characters")
    
    return msg

def parse_same_message(msg: str) -> Dict[str, Any]:
    """Parse SAME message with comprehensive validation."""
    msg = validate_same_message_format(msg)
    
    parts = msg[5:].rstrip('-').split('-')
    
    if len(parts) < 5:
        raise ValueError(f"Invalid SAME message format - expected at least 5 parts, got {len(parts)}: {parts}")
    
    originator = parts[0].strip()
    event_code = parts[1].strip()
    
    if not originator or not event_code:
        raise ValueError("Originator and event code cannot be empty")
    
    # Collect FIPS codes until we hit the part with '+'
    fips_codes = []
    duration = None
    timestamp = None
    station_id = None
    
    for i in range(2, len(parts)):
        if '+' in parts[i]:
            # Handle fips+duration as one token (e.g., '051000+0600')
            try:
                fips_part, duration = parts[i].split('+', 1)
                if fips_part.strip():
                    fips_codes.append(fips_part.strip())
            except ValueError:
                raise ValueError(f"Invalid duration format in part: {parts[i]}")
            
            try:
                timestamp = parts[i + 1].strip()
                station_id = parts[i + 2].strip()
            except IndexError:
                raise ValueError("Incomplete SAME message after duration")
            break
        else:
            fips_code = parts[i].strip()
            if fips_code:
                fips_codes.append(fips_code)
    
    # Validate required fields
    if not all([originator, event_code, duration, timestamp, station_id]):
        raise ValueError("Missing required fields in SAME message")
    
    if not fips_codes:
        raise ValueError("No valid FIPS codes found")
    
    # Validate duration format
    if not duration.isdigit() or len(duration) != 4:
        raise ValueError(f"Invalid duration format: {duration} (expected 4-digit number)")
    
    # Validate timestamp format
    if not timestamp.isdigit() or len(timestamp) != 7:
        raise ValueError(f"Invalid timestamp format: {timestamp} (expected 7-digit JJJHHMM)")
    
    return {
        "originator": originator,
        "event_code": event_code,
        "fips_codes": fips_codes,
        "duration": duration,
        "timestamp": timestamp,
        "station_id": station_id,
    }

def log_alert_to_db(alert: Dict[str, Any]):
    """Log alert to database with proper error handling."""
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT INTO alerts (
                    timestamp_utc, originator, event, event_code, fips_codes, regions,
                    duration_minutes, issued_code, source, raw_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert["timestamp_utc"],
                alert["originator"],
                alert["event"],
                alert.get("event_code", ""),
                ",".join(alert["fips_codes"]),
                ", ".join(alert["region_descriptions"]),
                alert["duration_minutes"],
                alert["issued_code"],
                alert["source"],
                alert["raw_message"]
            ))
            conn.commit()
            logger.info(f"Alert logged to database: {alert['event']} for {len(alert['fips_codes'])} regions")
    except Exception as e:
        logger.error(f"Failed to log alert to database: {e}")
        raise

def write_last_message(alert: Dict[str, Any]):
    """
    Write the most recent SAME alert to JSON file with error handling.
    Clean structured fields and convert times appropriately.
    """
    try:
        # Remove 'County' if every region contains it
        regions = alert['region_descriptions'].copy()
        if regions and all("County" in r for r in regions):
            regions = [r.replace(" County", "") for r in regions]
        
        # Convert UTC to local time string
        try:
            dt_utc = datetime.strptime(alert['timestamp_utc'], "%b %d %Y, %H:%M UTC")
            dt_local = dt_utc.replace(tzinfo=timezone.utc).astimezone()
            issued_local = dt_local.strftime("%b %d %Y, %-I:%M %p")
        except Exception as e:
            logger.warning(f"Time parse error, using original: {e}")
            issued_local = alert['timestamp_utc']
        
        # Prepare data for JSON
        message_data = {
            "event": alert['event'],
            "event_code": alert.get('event_code', ''),
            "originator": alert['originator'],
            "source": alert['source'],
            "issued_local": issued_local,
            "duration_minutes": alert['duration_minutes'],
            "regions": regions,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Write JSON to file atomically
        temp_path = f"{JSON_OUTPUT_PATH}.tmp"
        with open(temp_path, "w", encoding='utf-8') as f:
            json.dump(message_data, f, indent=2, ensure_ascii=False)
        
        # Atomic move
        os.rename(temp_path, JSON_OUTPUT_PATH)
        logger.info(f"Updated last message file: {alert['event']}")
        
    except Exception as e:
        logger.error(f"Failed to write last message file: {e}")
        # Clean up temp file if it exists
        temp_path = f"{JSON_OUTPUT_PATH}.tmp"
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        raise

def format_julian_timestamp(timestamp: str) -> str:
    """Format julian timestamp with comprehensive validation."""
    try:
        if not timestamp or not timestamp.isdigit() or len(timestamp) != 7:
            raise ValueError(f"Invalid timestamp format: {timestamp} (expected 7-digit JJJHHMM)")
        
        jjj = int(timestamp[:3])
        hh = int(timestamp[3:5])
        mm = int(timestamp[5:])
        
        # Validate ranges
        if not (1 <= jjj <= 366):
            raise ValueError(f"Invalid julian day: {jjj} (must be 1-366)")
        if not (0 <= hh <= 23):
            raise ValueError(f"Invalid hour: {hh} (must be 0-23)")
        if not (0 <= mm <= 59):
            raise ValueError(f"Invalid minute: {mm} (must be 0-59)")
        
        # Assuming current year; adjust as needed
        year = datetime.now(timezone.utc).year
        base_date = datetime(year, 1, 1, tzinfo=timezone.utc)
        msg_datetime = base_date + timedelta(days=jjj - 1, hours=hh, minutes=mm)
        
        return msg_datetime.strftime("%b %d %Y, %H:%M UTC")
    except Exception as e:
        logger.warning(f"Error formatting timestamp {timestamp}: {e}")
        return f"Invalid timestamp ({timestamp})"

def resolve_region_descriptions(fips_codes: List[str]) -> List[str]:
    """Resolve FIPS codes to region descriptions."""
    counties = _csv_cache.get('counties', {})
    region_descriptions = []
    
    for fips in fips_codes:
        entry = counties.get(fips)
        if entry and 'county' in entry:
            region_descriptions.append(entry['county'])
        else:
            region_descriptions.append(f"Unknown Region ({fips})")
            logger.warning(f"Unknown FIPS code: {fips}")
    
    return region_descriptions

def create_alert_data(parsed: Dict[str, Any], msg: str) -> Dict[str, Any]:
    """Create structured alert data from parsed message."""
    originators = _csv_cache.get('originators', {})
    events = _csv_cache.get('events', {})
    
    # Resolve descriptions
    origin = originators.get(parsed["originator"], {}).get("name", parsed["originator"])
    event = events.get(parsed["event_code"], {}).get("description", parsed["event_code"])
    
    # Parse timing
    issued_jjjhhmm = parsed["timestamp"]
    formatted_time = format_julian_timestamp(issued_jjjhhmm)
    duration_minutes = int(parsed['duration'])
    
    # Calculate end time
    try:
        dt_utc = datetime.strptime(formatted_time, "%b %d %Y, %H:%M UTC")
        end_time = dt_utc + timedelta(minutes=duration_minutes)
    except:
        end_time = None
    
    # Resolve regions
    region_descriptions = resolve_region_descriptions(parsed["fips_codes"])
    
    return {
        "originator": origin,
        "event": event,
        "event_code": parsed["event_code"],
        "fips_codes": parsed["fips_codes"],
        "region_descriptions": region_descriptions,
        "duration_minutes": duration_minutes,
        "timestamp_utc": formatted_time,
        "issued_code": parsed["timestamp"],
        "source": parsed["station_id"],
        "raw_message": msg,
        "end_time": end_time
    }

def print_alert_summary(alert: Dict[str, Any]):
    """Print formatted alert summary."""
    logger.info(f"📡 SAME Message Decoded:")
    logger.info(f"  Message    : {alert['raw_message']}")
    logger.info(f"  Originator : {alert['originator']}")
    logger.info(f"  Event      : {alert['event']}")
    logger.info(f"  Affected   : {', '.join(alert['region_descriptions'])}")
    logger.info(f"  Duration   : {alert['duration_minutes']} minutes")
    logger.info(f"  Issued     : {alert['timestamp_utc']}")
    
    if alert['end_time']:
        logger.info(f"  Ends       : {alert['end_time'].strftime('%b %d %Y, %H:%M UTC')}")
    
    logger.info(f"  Source     : {alert['source']}")
    logger.info(f"  ID         : {alert['event_code']}-{alert['issued_code']}")

def decode_same_message(msg: str):
    """Main message decoding function with comprehensive error handling."""
    try:
        # Parse the message
        parsed = parse_same_message(msg)
        
        # Create structured alert data
        alert = create_alert_data(parsed, msg)
        
        # Store the alert
        log_alert_to_db(alert)
        write_last_message(alert)
        
        # Display summary
        print_alert_summary(alert)
        
        logger.info(f"Successfully processed SAME message: {alert['event']}")
        
    except Exception as e:
        logger.error(f"Failed to decode SAME message '{msg}': {e}")
        raise

def main():
    """Main entry point with comprehensive error handling."""
    try:
        # Check for environment variable override
        env_msg = os.environ.get("SAMEDEC_MSG")
        
        if env_msg:
            logger.info("Processing message from environment variable")
            initialize_database()
            load_all_csv_data()
            decode_same_message(env_msg.strip())
        elif not sys.stdin.isatty():
            # Process piped input
            logger.info("Processing piped input")
            initialize_database()
            load_all_csv_data()
            piped_input = sys.stdin.read().strip()
            if piped_input:
                decode_same_message(piped_input)
            else:
                logger.warning("No input received from stdin")
        else:
            # Stream processing mode
            logger.info("Starting stream processing mode")
            stream_decode_from_stdin()
            
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()