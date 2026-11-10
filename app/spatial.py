from math import asin, cos, radians, sin, sqrt

from sqlalchemy import text
from sqlalchemy.orm import Session

NEAREST_OFFICER_SQL = text(
    """
    SELECT
        f.id AS facility_id,
        o.id AS officer_id,
        o.name AS officer_name,
        o.longitude AS officer_lng,
        o.latitude AS officer_lat,
        ROUND((ST_Distance(f.geom::geography, o.geom::geography) / 1000)::numeric, 1) AS km
    FROM health_facilities f
    CROSS JOIN LATERAL (
        SELECT id, name, longitude, latitude, geom
        FROM support_officers
        ORDER BY f.geom <-> geom
        LIMIT 1
    ) o
    """
)

WITHIN_20KM_SQL = text(
    """
    SELECT
        o.id AS officer_id,
        o.name AS officer_name,
        f.id AS facility_id,
        f.name AS facility_name,
        f.mahis_status,
        ROUND((ST_Distance(o.geom::geography, f.geom::geography) / 1000)::numeric, 1) AS km
    FROM support_officers o
    JOIN health_facilities f
        ON ST_DWithin(o.geom::geography, f.geom::geography, 20000)
    ORDER BY o.name, km
    """
)

DISTRICT_SUMMARY_SQL = text(
    """
    SELECT
        d.id,
        d.name AS district,
        d.region,
        COUNT(f.id) AS facilities,
        COUNT(f.id) FILTER (WHERE f.mahis_status = 'live') AS live,
        COUNT(f.id) FILTER (WHERE f.mahis_status = 'in_progress') AS in_progress,
        COUNT(f.id) FILTER (WHERE f.mahis_status = 'not_started') AS not_started,
        COUNT(f.id) FILTER (WHERE f.mahis_status = 'blocked') AS blocked,
        COUNT(f.id) FILTER (WHERE NOT f.has_trained_staff) AS unserved_by_trained_staff,
        COUNT(f.id) FILTER (WHERE NOT f.has_internet OR NOT f.has_power) AS remote_or_no_utilities,
        ST_AsGeoJSON(d.geom) AS geojson
    FROM districts d
    LEFT JOIN health_facilities f ON ST_Contains(d.geom, f.geom)
    GROUP BY d.id, d.name, d.region, d.geom
    ORDER BY live ASC, d.name
    """
)

CLUSTER_SQL = text(
    """
    SELECT
        id,
        name,
        latitude,
        longitude,
        mahis_status,
        ST_ClusterDBSCAN(geom, eps := 0.5, minpoints := 2) OVER () AS cluster_id
    FROM health_facilities
    WHERE mahis_status <> 'live'
    """
)

SUMMARY_SQL = text(
    """
    SELECT
        (SELECT COUNT(*) FROM districts) AS districts,
        COUNT(*) AS facilities,
        COUNT(*) FILTER (WHERE mahis_status = 'live') AS live,
        COUNT(*) FILTER (WHERE mahis_status = 'in_progress') AS in_progress,
        COUNT(*) FILTER (WHERE mahis_status = 'not_started') AS not_started,
        COUNT(*) FILTER (WHERE mahis_status = 'blocked') AS blocked,
        COUNT(*) FILTER (WHERE NOT has_internet OR NOT has_power) AS remote_or_no_utilities,
        COUNT(*) FILTER (WHERE NOT has_trained_staff) AS unserved_by_trained_staff
    FROM health_facilities
    """
)

ASSIGNED_SITES_SQL = text(
    """
    SELECT f.id, f.name, f.latitude, f.longitude, f.geom
    FROM health_facilities f
    CROSS JOIN LATERAL (
        SELECT o.id
        FROM support_officers o
        ORDER BY f.geom <-> o.geom
        LIMIT 1
    ) nearest
    WHERE f.mahis_status <> 'live'
      AND nearest.id = :officer_id
    """
)

ENSURE_DISTRICT_GEOM_SQL = text(
    """
    UPDATE districts d
    SET geom = sub.hull
    FROM (
        SELECT
            f.district_id,
            ST_Multi(ST_Buffer(ST_ConvexHull(ST_Collect(f.geom)), 0.25)) AS hull
        FROM health_facilities f
        GROUP BY f.district_id
    ) sub
    WHERE d.id = sub.district_id
      AND d.geom IS NULL
    """
)


def rows(db: Session, sql, **params) -> list[dict]:
    return [dict(row) for row in db.execute(sql, params).mappings()]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def greedy_route(sites: list[dict], start: dict | None = None) -> list[dict]:
    if not sites:
        return []
    remaining = sites[:]
    current = start or remaining.pop(0)
    if start and current in remaining:
        remaining.remove(current)
    path = [current]
    while remaining:
        nxt = min(
            remaining,
            key=lambda site: haversine_km(
                path[-1]["latitude"], path[-1]["longitude"], site["latitude"], site["longitude"]
            ),
        )
        remaining.remove(nxt)
        path.append(nxt)
    return path


def visit_route(db: Session, officer_id: int) -> dict:
    officer = db.execute(
        text("SELECT id, name, latitude, longitude FROM support_officers WHERE id = :id"),
        {"id": officer_id},
    ).mappings().first()
    if not officer:
        return {"officer": None, "stops": [], "method": "none"}

    sites = rows(db, ASSIGNED_SITES_SQL, officer_id=officer_id)
    start = {
        "id": 0,
        "name": officer["name"] + " (base)",
        "latitude": officer["latitude"],
        "longitude": officer["longitude"],
    }
    method = "greedy"
    ordered = greedy_route(sites, start=start)
    vertices = [{"vid": index + 1, **site} for index, site in enumerate([start] + sites)]

    if len(vertices) >= 2:
        try:
            db.execute(text("DROP TABLE IF EXISTS tmp_route_matrix"))
            db.execute(
                text("CREATE TEMP TABLE tmp_route_matrix (start_vid INT, end_vid INT, agg_cost FLOAT)")
            )
            for a in vertices:
                for b in vertices:
                    if a["vid"] == b["vid"]:
                        continue
                    db.execute(
                        text(
                            """
                            INSERT INTO tmp_route_matrix (start_vid, end_vid, agg_cost)
                            VALUES (:s, :t, :c)
                            """
                        ),
                        {
                            "s": a["vid"],
                            "t": b["vid"],
                            "c": haversine_km(
                                a["latitude"], a["longitude"], b["latitude"], b["longitude"]
                            ),
                        },
                    )
            tsp = rows(
                db,
                text(
                    """
                    SELECT seq, node
                    FROM pgr_TSP(
                        'SELECT start_vid, end_vid, agg_cost FROM tmp_route_matrix',
                        start_id := 1
                    )
                    ORDER BY seq
                    """
                ),
            )
            by_vid = {vertex["vid"]: vertex for vertex in vertices}
            tsp_path = [by_vid[int(item["node"])] for item in tsp if int(item["node"]) in by_vid]
            if tsp_path:
                ordered = tsp_path
                method = "pgRouting pgr_TSP"
        except Exception:
            db.rollback()
            ordered = greedy_route(sites, start=start)
            method = "greedy"

    stops = []
    total = 0.0
    for index, site in enumerate(ordered):
        km = 0.0
        if index:
            km = round(
                haversine_km(
                    ordered[index - 1]["latitude"],
                    ordered[index - 1]["longitude"],
                    site["latitude"],
                    site["longitude"],
                ),
                1,
            )
            total += km
        stops.append(
            {
                "seq": index + 1,
                "name": site["name"],
                "latitude": site["latitude"],
                "longitude": site["longitude"],
                "leg_km": km,
            }
        )
    return {
        "officer": dict(officer),
        "method": method,
        "total_km": round(total, 1),
        "stops": stops,
    }
