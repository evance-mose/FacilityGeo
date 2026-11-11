"""Load a DHIS2 org-unit GeoJSON export into the orgunits_raw staging table.

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/load_orgunits.py "/path/to/Organisation units.geojson"

Connection settings come from DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
(environment variables, or the gitignored .env file). Nothing is hard-coded.
The real export stays out of Git; pass its path on the command line.

Safe to re-run: rows are upserted by DHIS2 UID.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# Malawi bounding box (lon first). Anything outside is reported, not loaded.
LON_MIN, LON_MAX = 32.5, 36.0
LAT_MIN, LAT_MAX = -17.2, -9.2


def load_dotenv(path: Path) -> None:
    """Tiny .env reader; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def connect():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    missing = [k for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD") if k not in os.environ]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def read_features(path: Path):
    data = json.loads(path.read_text())
    rows, rejected = [], []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        uid = props.get("id") or feature.get("id")
        geometry = feature.get("geometry")
        if not uid or not props.get("name"):
            rejected.append((uid, "missing id or name"))
            continue
        if not geometry or geometry.get("type") != "Point":
            rejected.append((uid, "no point geometry"))
            continue
        lon, lat = geometry["coordinates"][:2]
        if not (LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX):
            rejected.append((uid, f"outside Malawi ({lon}, {lat})"))
            continue
        rows.append((uid, props["name"], props.get("parentName"), props.get("level"), json.dumps(geometry)))
    return rows, rejected


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1]).expanduser()
    rows, rejected = read_features(path)

    with connect() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO orgunits_raw (id, name, parentname, level, geom)
            VALUES %s
            ON CONFLICT (id) DO UPDATE
               SET name = EXCLUDED.name,
                   parentname = EXCLUDED.parentname,
                   level = EXCLUDED.level,
                   geom = EXCLUDED.geom
            """,
            rows,
            template="(%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
        )
        cur.execute("SELECT COUNT(*) FROM orgunits_raw")
        total = cur.fetchone()[0]

    print(f"read {len(rows) + len(rejected)} features, loaded {len(rows)}, rejected {len(rejected)}")
    for uid, reason in rejected:
        print(f"  rejected {uid}: {reason}")
    print(f"orgunits_raw now holds {total} rows")


if __name__ == "__main__":
    main()
