"""Compare PostGIS results with the QGIS processing cross-checks.

QGIS (via the MCP tools) writes two files into data/:
  qgis_check_counts.geojson   native:countpointsinpolygon  (districts_hdx x facilities)
  qgis_check_nearest.geojson  native:joinbynearest         (facilities -> officers, planar)

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/compare_qgis_checks.py

Expected: district counts identical; nearest officer identical except for a few
facilities where two officers are almost equally far. QGIS measures in degrees
(planar) while PostGIS uses ::geography (metres), so near-ties can flip.
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
        cur.execute(
            """SELECT f.id, f.support_officer_id,
                      round(ST_Distance(f.geom::geography, o.geom::geography)),
                      (SELECT round(min(ST_Distance(f.geom::geography, o2.geom::geography)))
                       FROM support_officers o2 WHERE o2.id <> f.support_officer_id)
               FROM facilities f JOIN support_officers o ON o.id = f.support_officer_id"""
        )
        assigned = {r[0]: r[1:] for r in cur.fetchall()}

    counts = {f["properties"]["name"]: int(f["properties"]["NUMPOINTS"])
              for f in json.loads((DATA / "qgis_check_counts.geojson").read_text())["features"]}
    nearest = {f["properties"]["id"]: f["properties"]["officer_id"]
               for f in json.loads((DATA / "qgis_check_nearest.geojson").read_text())["features"]}

    differ = {k: (sql_counts[k], counts.get(k)) for k in sql_counts if sql_counts[k] != counts.get(k)}
    print(f"1. Facilities per district polygon: {len(sql_counts)} polygons, "
          f"PostGIS {sum(sql_counts.values())} vs QGIS {sum(counts.values())}; differences: {differ or 'none'}")

    flips = [(i, a[0], nearest[i], a[1], a[2]) for i, a in assigned.items() if nearest.get(i) != a[0]]
    print(f"2. Nearest officer: {len(assigned) - len(flips)} of {len(assigned)} agree; {len(flips)} differ")
    for i, pg, qg, metres, other in flips:
        print(f"   facility {i}: PostGIS officer {pg} ({int(metres)} m) vs QGIS officer {qg} "
              f"({int(other)} m): gap {int(other - metres)} m (degrees vs metres near-tie)")


if __name__ == "__main__":
    main()
