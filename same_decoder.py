import csv
import os
import sys
import sqlite3
import json

from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta, timezone


DATA_DIR =  Path(os.path.join(os.path.dirname(__file__), "data"))


def stream_decode_from_stdin():
    buffer = ""

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
                print(f"❌ Error decoding: {buffer}\n{e}")
            buffer = ""


def load_csv_to_dict(filename: str, key_field: str) -> Dict[str, Dict[str, str]]:
    path = DATA_DIR / filename
    with path.open() as f:
        reader = csv.DictReader(f)
        return {row[key_field]: row for row in reader}


def parse_same_message(msg: str) -> Dict:
    if not msg.startswith("ZCZC-"):
        raise ValueError("Message must start with 'ZCZC-'")

    parts = msg[5:].rstrip('-').split('-')

    if len(parts) < 5:
        raise ValueError(f"Unexpected SAME message format with {len(parts)} parts: {parts}")

    originator = parts[0]
    event_code = parts[1]

    # Collect FIPS codes until we hit the part with '+'
    fips_codes = []
    duration = None
    timestamp = None
    station_id = None

    for i in range(2, len(parts)):
        if '+' in parts[i]:
            # Handle fips+duration as one token (e.g., '051000+0600')
            fips_part, duration = parts[i].split('+', 1)
            fips_codes.append(fips_part)

            try:
                timestamp = parts[i + 1]
                station_id = parts[i + 2]
            except IndexError:
                raise ValueError("Incomplete SAME message after duration")
            break
        else:
            fips_codes.append(parts[i])

    if not (originator and event_code and duration and timestamp and station_id and fips_codes):
        raise ValueError("Missing required fields in SAME message")

    return {
        "originator": originator,
        "event_code": event_code,
        "fips_codes": fips_codes,
        "duration": duration,
        "timestamp": timestamp,
        "station_id": station_id,
    }


def log_alert_to_db(alert: dict):
    conn = sqlite3.connect("alerts.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO alerts (
            timestamp_utc, originator, event, fips_codes, regions,
            duration_minutes, issued_code, source, raw_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        alert["timestamp_utc"],
        alert["originator"],
        alert["event"],
        ",".join(alert["fips_codes"]),
        ", ".join(alert["region_descriptions"]),
        alert["duration_minutes"],
        alert["issued_code"],
        alert["source"],
        alert["raw_message"]
    ))
    conn.commit()
    conn.close()


def write_last_message(alert: dict):
    """
    Writes the most recent SAME alert to last_message.json with
    clean structured fields. Removes redundant 'County' if all
    regions contain it. Converts issued time to local (no pytz).
    """
    # Remove 'County' if every region contains it
    regions = alert['region_descriptions']
    if all("County" in r for r in regions):
        regions = [r.replace(" County", "") for r in regions]

    # Convert UTC to local time string
    try:
        dt_utc = datetime.strptime(alert['timestamp_utc'], "%b %d %Y, %H:%M UTC")
        dt_local = dt_utc.replace(tzinfo=timezone.utc).astimezone()
        issued_local = dt_local.strftime("%b %d %Y, %-I:%M %p")  # e.g. Aug 06 2025, 4:00 PM
    except Exception as e:
        print(f"⚠️ Time parse error: {e}")
        issued_local = alert['timestamp_utc']  # fallback to original string

    # Prepare data for JSON
    message_data = {
        "event": alert['event'],
        "event_code": alert.get('event_code', ''),  # keep blank if unknown
        "originator": alert['originator'],
        "source": alert['source'],
        "issued_local": issued_local,
        "duration_minutes": alert['duration_minutes'],
        "regions": regions,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Write JSON to file
    with open("last_message.json", "w") as f:
        json.dump(message_data, f, indent=2)


def format_julian_timestamp(timestamp: str) -> str:
    try:
        if len(timestamp) != 7:
            raise ValueError("Timestamp must be in JJJHHMM format")

        jjj = int(timestamp[:3])
        hh = int(timestamp[3:5])
        mm = int(timestamp[5:])

        # Assuming current year; adjust as needed
        year = datetime.now(timezone.utc).year
        base_date = datetime(year, 1, 1)
        msg_datetime = base_date + timedelta(days=jjj - 1, hours=hh, minutes=mm)

        return msg_datetime.strftime("%b %d %Y, %H:%M UTC")
    except Exception as e:
        return f"Invalid timestamp ({timestamp}): {e}"



def decode_same_message(msg: str):
    print(f"📡 SAME Message Decoded:")
    print(f"  Message    : {msg}")

    originators = load_csv_to_dict("originators.csv", "code")
    events = load_csv_to_dict("eas_events.csv", "code")
    counties = load_csv_to_dict("fips_counties.csv", "fips")
    states = load_csv_to_dict("fips_states.csv", "code")

    parsed = parse_same_message(msg)

    origin = originators.get(parsed["originator"], {}).get("name", parsed["originator"])
    event = events.get(parsed["event_code"], {}).get("description", parsed["event_code"])

    issued_jjjhhmm = parsed["timestamp"]
    julian_day = int(issued_jjjhhmm[:3])
    hour = int(issued_jjjhhmm[3:5])
    minute = int(issued_jjjhhmm[5:7])
    year = datetime.now(timezone.utc).year
    issued_datetime = datetime(year, 1, 1, hour, minute, tzinfo=timezone.utc) + timedelta(days=julian_day - 1)
    formatted_time = format_julian_timestamp(issued_jjjhhmm)
    duration_minutes = int(parsed['duration'])
    end_time = issued_datetime + timedelta(minutes=duration_minutes)


    region_descriptions: List[str] = []
    for fips in parsed["fips_codes"]:
        entry = counties.get(fips)
        if entry:
            region_descriptions.append(f"{entry['county']}")
        else:
            region_descriptions.append(f"Unknown Region ({fips})")

    alert = {
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
    }

    log_alert_to_db(alert)
    write_last_message(alert)


    print(f"  Originator : {origin}")
    print(f"  Event      : {event}")
    print(f"  Affected   : {', '.join(region_descriptions)}")
    print(f"  Duration   : {duration_minutes} minutes")
    print(f"  Issued     : {formatted_time}")
    print(f"  Ends       : {end_time.strftime('%b %d %Y, %H:%M UTC')}")
    print(f"  Source     : {parsed['station_id']}")
    print(f"  ID         : {parsed['originator']}-{parsed['event_code']}-{issued_jjjhhmm}")


if __name__ == "__main__":
    # Check if SAMEDEC_MSG is set in the environment
    # env_msg = os.environ.get("SAMEDEC_MSG")

    # if env_msg:
    #     decode_same_message(env_msg.strip())
    # elif not sys.stdin.isatty():
    #     piped_input = sys.stdin.read().strip()
    #     if piped_input:
    #         decode_same_message(piped_input)
    #     else:
    #         print("⚠️ No input received from stdin.")
    # else:
    #     test_message = "ZasdadsCZC-EAS-RWT-012057-012081-012101-012103-012115+0030-2780415-WTSP/TV-"
    #     print("ℹ️ No input detected, using test message...\n")
    #     decode_same_message(test_message)
    stream_decode_from_stdin()    