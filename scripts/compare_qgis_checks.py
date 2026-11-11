"""Compare PostGIS results with a QGIS processing cross-check.

QGIS (via the MCP tools) writes a file into data/:
  qgis_check_counts.geojson   native:countpointsinpolygon  (districts_hdx x facilities)

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/compare_qgis_checks.py

Expected: district counts identical. (A nearest-officer comparison existed while
simulated officers were loaded; it was removed with them. Add one back when real
officers are loaded.)
"""
import json
from pathlib import Path

from load_orgunits import connect

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT d.name, count(f.id) FROM districts_hdx d "
            "LEFT JOIN facilities f ON ST_Contains(d.geom, f.geom) GROUP BY d.name"
        )
        sql_counts = dict(cur.fetchall())

    counts = {f["properties"]["name"]: int(f["properties"]["NUMPOINTS"])
              for f in json.loads((DATA / "qgis_check_counts.geojson").read_text())["features"]}

    differ = {k: (sql_counts[k], counts.get(k)) for k in sql_counts if sql_counts[k] != counts.get(k)}
    print(f"Facilities per district polygon: {len(sql_counts)} polygons, "
          f"PostGIS {sum(sql_counts.values())} vs QGIS {sum(counts.values())}; differences: {differ or 'none'}")


if __name__ == "__main__":
    main()
