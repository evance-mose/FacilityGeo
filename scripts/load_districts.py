"""Load the HDX district polygons (GeoJSON, EPSG:4326) into districts_hdx.

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/load_districts.py data/mw_districts.geojson

The GeoJSON is made from the HDX shapefile with:
    ogr2ogr -f GeoJSON data/mw_districts.geojson data/mw_districts/mw_districts.shp \
        -t_srs EPSG:4326 -lco RFC7946=YES -nlt PROMOTE_TO_MULTI

Connection settings come from DB_* (environment or gitignored .env).
Safe to re-run: rows are upserted by district name.

The source file has inconsistent attributes, cleaned here:
  * names are upper case except 'Mwanza' -> all become Title Case (as in DHIS2)
  * region is null for Chikwawa/Neno and 'SOUTH' is used for 'SOUTHERN'
"""
import json
import sys
from pathlib import Path

from psycopg2.extras import execute_values

from load_orgunits import connect

REGION_FIXES = {"SOUTH": "Southern"}
# Region missing in the source file; both are in the Southern region.
MISSING_REGION = {"Chikwawa": "Southern", "Neno": "Southern"}


def clean_name(raw: str) -> str:
    return " ".join(raw.strip().title().split())


def read_features(path: Path):
    data = json.loads(path.read_text())
    rows, rejected = [], []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry")
        raw_name = props.get("district")
        if not raw_name:
            rejected.append(("?", "missing district name"))
            continue
        name = clean_name(raw_name)
        if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
            rejected.append((name, "no polygon geometry"))
            continue
        raw_region = (props.get("region") or "").strip().upper()
        region = REGION_FIXES.get(raw_region, raw_region.title()) or MISSING_REGION.get(name)
        rows.append((name, region, json.dumps(geometry)))
    return rows, rejected


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rows, rejected = read_features(Path(sys.argv[1]).expanduser())

    with connect() as conn, conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO districts_hdx (name, region, geom)
            VALUES %s
            ON CONFLICT (name) DO UPDATE
               SET region = EXCLUDED.region, geom = EXCLUDED.geom
            """,
            rows,
            template="(%s, %s, ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))))",
        )
        cur.execute("SELECT COUNT(*) FROM districts_hdx")
        total = cur.fetchone()[0]

    print(f"read {len(rows) + len(rejected)} features, loaded {len(rows)}, rejected {len(rejected)}")
    for name, reason in rejected:
        print(f"  rejected {name}: {reason}")
    print(f"districts_hdx now holds {total} rows")


if __name__ == "__main__":
    main()
