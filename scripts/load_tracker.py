"""Load a rollout tracker CSV into the tracker_raw staging table.

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/load_tracker.py data/tracker.csv
(a spreadsheet can be converted first with scripts/xlsx_to_csv.py)

Headers are mapped by name (case and punctuation ignored, see ALIASES), so
the real file does not need renaming. Everything is stored as text; cleaning
happens in database/match_tracker.sql. Re-running REPLACES the staging rows
(tracker_raw is a staging table, rebuilt from the CSV each time).

Connection settings come from DB_* (environment or gitignored .env).
The real tracker stays out of Git (data/ is ignored).
"""
import csv
import re
import sys
from pathlib import Path

from psycopg2.extras import execute_values

from load_orgunits import connect

ALIASES = {
    "facility_name": {"facilityname", "name", "facility", "healthfacility", "site", "sitename", "facilitysite"},
    "district": {"district", "districtname", "districtlocation"},
    "facility_code": {"dhis2code", "code", "facilitycode", "uid", "dhis2uid", "orgunitid", "orgunituid"},
    "status": {"status", "deploymentstatus", "rolloutstatus", "implementationstatus", "golivestatus"},
    "training": {"endusertraining", "training", "trainingstatus", "usertraining"},
    "go_live_date": {"golivedate", "golive", "livedate", "dategolive", "datelive"},
    "devices": {"devicesinstalled", "devices", "computers", "devicesdeployed"},
    "staff_trained": {"stafftrained", "trained", "numbertrained", "trainedstaff"},
    "internet": {"internet", "hasinternet", "connectivity", "internetavailable"},
    "power": {"power", "haspower", "electricity", "poweravailable"},
}
REQUIRED = ("facility_name", "district")


def key(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower())


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1]).expanduser()
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        mapping, ignored = {}, []
        for header in reader.fieldnames or []:
            column = next((c for c, names in ALIASES.items() if key(header) in names), None)
            if column and column not in mapping.values():
                mapping[header] = column
            else:
                ignored.append(header)
        missing = [c for c in REQUIRED if c not in mapping.values()]
        if missing:
            sys.exit(f"CSV is missing required column(s): {', '.join(missing)}. Headers seen: {reader.fieldnames}")
        columns = list(mapping.values())
        rows = [tuple((rec[h] or "").strip() or None for h in mapping) for rec in reader]

    with connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tracker_raw")
        execute_values(cur, f"INSERT INTO tracker_raw ({', '.join(columns)}) VALUES %s", rows)
        cur.execute("SELECT COUNT(*) FROM tracker_raw")
        total = cur.fetchone()[0]

    print(f"read {len(rows)} rows from {path.name}")
    print("mapped columns:", ", ".join(f"{h!r} -> {c}" for h, c in mapping.items()))
    if ignored:
        print("ignored columns:", ", ".join(map(repr, ignored)))
    print(f"tracker_raw now holds {total} rows")


if __name__ == "__main__":
    main()
