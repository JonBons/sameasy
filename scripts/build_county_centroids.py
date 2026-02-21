#!/usr/bin/env python3
"""
Build data/county_centroids.csv from Census CenPop2020 Mean Center of Population.
Used for point->FIPS lookup in the alerts API (nearest county to lat,lon).
Run once to populate the file; safe to re-run (overwrites).
"""
import csv
import sys
from pathlib import Path
from urllib.request import urlopen

CENSUS_URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"
PROJECT_ROOT = Path(__file__).parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "county_centroids.csv"


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(CENSUS_URL, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Failed to fetch Census data: {e}", file=sys.stderr)
        return 1

    lines = raw.strip().splitlines()
    if not lines:
        print("Empty Census response", file=sys.stderr)
        return 1
    # Header: STATEFP,COUNTYFP,COUNAME,STNAME,POPULATION,LATITUDE,LONGITUDE
    rows = []
    for i, line in enumerate(lines):
        if i == 0:
            continue  # skip header
        parts = next(csv.reader([line]), [])
        if len(parts) < 7:
            continue
        state = ("000" + (parts[0] or "").strip())[-3:]
        county = ("000" + (parts[1] or "").strip())[-3:]
        lat = (parts[5] or "0").strip().lstrip("+")
        lon = (parts[6] or "0").strip().lstrip("+")
        if state == "000" and county == "000":
            continue
        fips = state + county
        rows.append({"fips": fips, "lat": lat, "lon": lon})

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fips", "lat", "lon"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} counties to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
