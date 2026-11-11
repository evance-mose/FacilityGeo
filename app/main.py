"""FacilityGeo API: spatial monitoring of the rollout across Malawi's health facilities.

Run locally (from the FacilityGeo folder):
    .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

SECURITY: this API has NO authentication and is meant to run on localhost only.
Production use would need authentication and authorisation (for example OAuth2
or a Ministry single sign-on), HTTPS, role checks on POST/PATCH, and audit
logging of status changes. Holds no patient data: facility-level records only.

Spatial conventions: longitude comes first in ST_MakePoint(lon, lat); distances
in metres use ::geography; clustering runs in EPSG:32736 (UTM 36S, metres).
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

import psycopg2
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import ROOT
from .schemas import FacilityCreate, FilterStatus, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, Status, StatusUpdate

log = logging.getLogger("facilitygeo")
FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="FacilityGeo",
    summary="Spatial monitoring of the rollout across health facilities in Malawi",
    description=(
        "Deployment gaps, clusters of facilities not yet started, and nearest support "
        "officer, backed by PostgreSQL + PostGIS. No authentication: local use only."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(psycopg2.Error)
async def database_error(_: Request, exc: psycopg2.Error):
    log.exception("database error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "database error"})


# --------------------------------------------------------------------- helpers
FACILITY_COLS = """
    f.id, f.facility_code, f.name, f.district, f.facility_type, f.deployment_status, f.training_status,
    f.go_live_date, f.devices_installed, f.staff_trained, f.has_internet, f.has_power,
    f.match_method, f.support_officer_id, o.name AS support_officer,
    ST_AsGeoJSON(f.geom, 6)::json AS geometry
"""

# Nearest officer to {pt}: <-> (KNN, degrees, index-assisted) picks 3 candidates,
# then the true nearest is chosen by distance in metres (::geography).
# LEFT JOIN ... ON TRUE: with no officers loaded the row is kept and officer_* are NULL.
NEAREST_OFFICER = """
    LEFT JOIN LATERAL (
        SELECT c.id AS officer_id, c.name AS officer_name, c.base_location,
               ST_Distance(c.geom::geography, ({pt})::geography) AS distance_m,
               ST_AsGeoJSON(c.geom, 6)::json AS officer_geometry
        FROM (SELECT id, name, base_location, geom FROM support_officers
              ORDER BY geom <-> {pt} LIMIT 3) c
        ORDER BY distance_m LIMIT 1
    ) n ON TRUE
"""

DISTRICT_POLYGON = "CASE WHEN f.district LIKE 'Mzimba %%' THEN 'Mzimba' ELSE f.district END"


def feature_collection(rows, **extra) -> dict:
    features = []
    for row in rows:
        props = dict(row)
        geometry = props.pop("geometry")
        features.append({"type": "Feature", "id": props.get("id"), "geometry": geometry, "properties": props})
    return {"type": "FeatureCollection", **extra, "features": features}


def one_facility(cur, facility_id: int) -> Optional[dict]:
    cur.execute(
        f"SELECT {FACILITY_COLS} FROM facilities f "
        "LEFT JOIN support_officers o ON o.id = f.support_officer_id WHERE f.id = %s",
        (facility_id,),
    )
    row = cur.fetchone()
    return feature_collection([row])["features"][0] if row else None


# --------------------------------------------------------------------- system
@app.get("/health", tags=["system"])
def health():
    with db.cursor() as cur:
        cur.execute("SELECT PostGIS_Version() AS postgis")
        return {"status": "ok", **cur.fetchone()}


@app.get("/", include_in_schema=False)
def index():
    page = FRONTEND / "index.html"
    if not page.exists():
        raise HTTPException(404, "frontend/index.html not found")
    return FileResponse(page)


# ------------------------------------------------------------------ facilities
@app.get("/facilities", tags=["facilities"])
def list_facilities(
    status: Optional[FilterStatus] = None,
    district: Optional[str] = Query(default=None, max_length=60),
    limit: int = Query(default=2000, ge=1, le=5000),
):
    """Facilities as GeoJSON, optionally filtered by deployment status and DHIS2 district."""
    with db.cursor() as cur:
        cur.execute(
            f"""SELECT {FACILITY_COLS}
                FROM facilities f LEFT JOIN support_officers o ON o.id = f.support_officer_id
                WHERE (%(status)s::text IS NULL OR f.deployment_status = %(status)s)
                  AND (%(district)s::text IS NULL OR f.district = %(district)s)
                ORDER BY f.id LIMIT %(limit)s""",
            {"status": status, "district": district, "limit": limit},
        )
        rows = cur.fetchall()
    return feature_collection(rows, count=len(rows))


@app.post("/facilities", status_code=201, tags=["facilities"])
def create_facility(body: FacilityCreate):
    """Add a facility. Coordinates must lie inside Malawi's bounding box
    (lat -17.2..-9.2, lon 32.5..36.0); the nearest officer is assigned."""
    with db.cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM facilities WHERE district = %s LIMIT 1", (body.district,))
        if cur.fetchone() is None:
            cur.execute("SELECT DISTINCT district FROM facilities ORDER BY 1")
            known = [r["district"] for r in cur.fetchall()]
            raise HTTPException(422, f"Unknown district '{body.district}'. Known districts: {', '.join(known)}")
        try:
            cur.execute(
                """INSERT INTO facilities
                     (facility_code, name, district, facility_type, deployment_status, go_live_date,
                      devices_installed, staff_trained, has_internet, has_power, match_method, geom)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual',
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                   RETURNING id""",
                (body.facility_code, body.name, body.district, body.facility_type, body.deployment_status,
                 body.go_live_date, body.devices_installed, body.staff_trained, body.has_internet,
                 body.has_power, body.longitude, body.latitude),  # longitude first
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(409, f"facility_code '{body.facility_code}' already exists")
        new_id = cur.fetchone()["id"]
        cur.execute(
            """UPDATE facilities f SET support_officer_id = (
                   SELECT c.id FROM (SELECT id, geom FROM support_officers
                                     ORDER BY geom <-> f.geom LIMIT 3) c
                   ORDER BY ST_Distance(c.geom::geography, f.geom::geography) LIMIT 1)
               WHERE f.id = %s""",
            (new_id,),
        )
        cur.execute(
            f"""SELECT NOT EXISTS (SELECT 1 FROM districts_hdx d
                                   WHERE d.name = {DISTRICT_POLYGON} AND ST_Intersects(d.geom, f.geom)) AS outside
                FROM facilities f WHERE f.id = %s""",
            (new_id,),
        )
        outside = cur.fetchone()["outside"]
        feature = one_facility(cur, new_id)
    warnings = []
    if outside:
        warnings.append("Point is outside this district's polygon (boundary data is coarse; check the coordinates).")
    return {"facility": feature, "warnings": warnings}


@app.patch("/facilities/{facility_id}/status", tags=["facilities"])
def update_status(facility_id: int, body: StatusUpdate):
    """Change deployment status. Moving to 'live' stamps go_live_date (if empty);
    moving away from 'live' clears it."""
    with db.cursor(commit=True) as cur:
        cur.execute(
            """UPDATE facilities
               SET deployment_status = %(s)s::text,
                   go_live_date = CASE WHEN %(s)s::text = 'live'
                                       THEN coalesce(go_live_date, CURRENT_DATE) ELSE NULL END
               WHERE id = %(id)s
               RETURNING id, name, deployment_status, go_live_date""",
            {"s": body.deployment_status, "id": facility_id},
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, f"facility {facility_id} not found")
    return row


# ------------------------------------------------------------------ statistics
@app.get("/stats/summary", tags=["statistics"])
def summary():
    """Headline numbers. pct_live is the share of TRACKED facilities that are live
    (facilities with no tracker row are counted as not_in_tracker, not as not started)."""
    with db.cursor() as cur:
        cur.execute(
            """SELECT count(*) AS facilities,
                      count(DISTINCT district) AS districts,
                      count(*) FILTER (WHERE deployment_status <> 'not_in_tracker') AS tracked,
                      count(*) FILTER (WHERE deployment_status = 'live') AS live,
                      count(*) FILTER (WHERE deployment_status = 'in_progress') AS in_progress,
                      count(*) FILTER (WHERE deployment_status = 'not_started') AS not_started,
                      count(*) FILTER (WHERE deployment_status = 'not_in_tracker') AS not_in_tracker,
                      round(100.0 * count(*) FILTER (WHERE deployment_status = 'live')
                            / nullif(count(*) FILTER (WHERE deployment_status <> 'not_in_tracker'), 0), 1) AS pct_live,
                      count(*) FILTER (WHERE training_status = 'done') AS training_done,
                      count(*) FILTER (WHERE training_status = 'in_progress') AS training_in_progress,
                      count(*) FILTER (WHERE training_status = 'not_started') AS training_not_started,
                      count(has_internet) AS internet_recorded,
                      count(has_power) AS power_recorded,
                      count(*) FILTER (WHERE has_internet IS FALSE) AS no_internet,
                      count(*) FILTER (WHERE has_power IS FALSE) AS no_power,
                      (SELECT count(*) FROM support_officers) AS officers
               FROM facilities"""
        )
        return cur.fetchone()


@app.get("/stats/districts", tags=["statistics"])
def district_stats(sort: str = Query(default="name", pattern="^(name|pct_live_desc|pct_live_asc)$")):
    """Per-district counts and % live of the tracked facilities (NULL when none are tracked).
    sort=pct_live_asc lists the districts furthest behind first; untracked districts go last."""
    order = {
        "name": "district",
        "pct_live_desc": "pct_live DESC NULLS LAST, district",
        "pct_live_asc": "pct_live ASC NULLS LAST, district",
    }[sort]  # whitelisted: never interpolates user text
    with db.cursor() as cur:
        cur.execute(
            f"""SELECT district,
                       count(*) AS total,
                       count(*) FILTER (WHERE deployment_status <> 'not_in_tracker') AS tracked,
                       count(*) FILTER (WHERE deployment_status = 'live') AS live,
                       count(*) FILTER (WHERE deployment_status = 'in_progress') AS in_progress,
                       count(*) FILTER (WHERE deployment_status = 'not_started') AS not_started,
                       count(*) FILTER (WHERE deployment_status = 'not_in_tracker') AS not_in_tracker,
                       round(100.0 * count(*) FILTER (WHERE deployment_status = 'live')
                             / nullif(count(*) FILTER (WHERE deployment_status <> 'not_in_tracker'), 0), 1) AS pct_live,
                       rank() OVER (ORDER BY count(*) FILTER (WHERE deployment_status = 'live')::numeric
                                             / nullif(count(*) FILTER (WHERE deployment_status <> 'not_in_tracker'), 0)
                                             DESC NULLS LAST) AS rank_by_pct_live
                FROM facilities GROUP BY district ORDER BY {order}"""
        )
        return cur.fetchall()


@app.get("/districts", tags=["statistics"])
def districts_geojson():
    """HDX district polygons (simplified for drawing) with % live of the tracked facilities.
    Mzimba North and South are combined because the HDX file has a single Mzimba polygon."""
    with db.cursor() as cur:
        cur.execute(
            f"""SELECT d.id, d.name, d.region,
                       count(f.id) AS total,
                       count(f.id) FILTER (WHERE f.deployment_status <> 'not_in_tracker') AS tracked,
                       count(f.id) FILTER (WHERE f.deployment_status = 'live') AS live,
                       round(100.0 * count(f.id) FILTER (WHERE f.deployment_status = 'live')
                             / nullif(count(f.id) FILTER (WHERE f.deployment_status <> 'not_in_tracker'), 0), 1) AS pct_live,
                       ST_AsGeoJSON(ST_SimplifyPreserveTopology(d.geom, 0.003), 5)::json AS geometry
                FROM districts_hdx d
                LEFT JOIN facilities f ON {DISTRICT_POLYGON} = d.name
                GROUP BY d.id ORDER BY d.name"""
        )
        return feature_collection(cur.fetchall())


@app.get("/officers", tags=["statistics"])
def officers():
    """Support officers with how many facilities each is assigned (empty until real officers are loaded)."""
    with db.cursor() as cur:
        cur.execute(
            """SELECT s.id, s.name, s.base_location, s.is_simulated,
                      (SELECT count(*) FROM facilities f WHERE f.support_officer_id = s.id) AS facilities,
                      ST_AsGeoJSON(s.geom, 6)::json AS geometry
               FROM support_officers s ORDER BY s.id"""
        )
        return feature_collection(cur.fetchall())


# -------------------------------------------------------------------- analysis
@app.get("/analysis/nearest-officer", tags=["analysis"])
def nearest_officer(facility_id: int = Query(ge=1)):
    """Nearest support officer to a facility (KNN with <->, distance in metres via ::geography)."""
    with db.cursor() as cur:
        cur.execute(
            f"""SELECT f.id, f.name, f.district, f.support_officer_id,
                       n.officer_id, n.officer_name, n.base_location, round(n.distance_m) AS distance_m,
                       ST_AsGeoJSON(ST_MakeLine(f.geom, (SELECT geom FROM support_officers WHERE id = n.officer_id)), 6)::json AS line
                FROM facilities f {NEAREST_OFFICER.format(pt='f.geom')}
                WHERE f.id = %s""",
            (facility_id,),
        )
        r = cur.fetchone()
    if r is None:
        raise HTTPException(404, f"facility {facility_id} not found")
    if r["officer_id"] is None:
        raise HTTPException(404, "No support officers are loaded yet (table support_officers is empty).")
    return {
        "facility": {"id": r["id"], "name": r["name"], "district": r["district"]},
        "officer": {"id": r["officer_id"], "name": r["officer_name"], "base_location": r["base_location"]},
        "distance_m": r["distance_m"],
        "distance_km": round(float(r["distance_m"]) / 1000, 1),
        "matches_assigned_officer": r["support_officer_id"] == r["officer_id"],
        "line": r["line"],
    }


@app.get("/analysis/within-radius", tags=["analysis"])
def within_radius(
    lat: float = Query(ge=LAT_MIN, le=LAT_MAX),
    lon: float = Query(ge=LON_MIN, le=LON_MAX),
    radius_km: float = Query(default=20, gt=0, le=500),
    status: Optional[FilterStatus] = None,
    limit: int = Query(default=2000, ge=1, le=5000),
):
    """Facilities within radius_km of a point (ST_DWithin on geography, so metres)."""
    with db.cursor() as cur:
        cur.execute(
            f"""WITH p AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS geom)
                SELECT {FACILITY_COLS}, round(ST_Distance(f.geom::geography, p.geom::geography)) AS distance_m
                FROM facilities f CROSS JOIN p
                LEFT JOIN support_officers o ON o.id = f.support_officer_id
                WHERE ST_DWithin(f.geom::geography, p.geom::geography, %(metres)s)
                  AND (%(status)s::text IS NULL OR f.deployment_status = %(status)s)
                ORDER BY distance_m LIMIT %(limit)s""",
            {"lon": lon, "lat": lat, "metres": radius_km * 1000, "status": status, "limit": limit},
        )
        rows = cur.fetchall()
    by_status = {}
    for r in rows:
        by_status[r["deployment_status"]] = by_status.get(r["deployment_status"], 0) + 1
    return feature_collection(rows, count=len(rows), radius_km=radius_km, by_status=by_status,
                              centre={"lat": lat, "lon": lon})


@app.get("/analysis/clusters", tags=["analysis"])
def clusters(
    eps_km: float = Query(default=15, ge=1, le=200, description="DBSCAN distance in km (converted to metres); "
                                                              "large values chain dense areas into one cluster"),
    min_points: int = Query(default=5, ge=2, le=100),
    status: FilterStatus = "not_started",
):
    """Clusters of facilities with the given status (default: not started), found with
    ST_ClusterDBSCAN in EPSG:32736 so eps is in metres. Each cluster gets its nearest officer."""
    params = {"eps": eps_km * 1000.0, "minpts": min_points, "status": status}
    with db.cursor() as cur:
        cur.execute(
            f"""WITH pts AS (
                    SELECT id, name, district, geom,
                           ST_ClusterDBSCAN(ST_Transform(geom, 32736), eps := %(eps)s, minpoints := %(minpts)s) OVER () AS cid
                    FROM facilities WHERE deployment_status = %(status)s
                ), cl AS (
                    SELECT cid, count(*) AS size, array_agg(id ORDER BY id) AS facility_ids,
                           array_agg(DISTINCT district ORDER BY district) AS districts,
                           ST_Collect(geom) AS coll
                    FROM pts WHERE cid IS NOT NULL GROUP BY cid
                )
                SELECT cl.cid AS cluster_id, cl.size, cl.facility_ids, cl.districts,
                       ST_AsGeoJSON(ST_ConvexHull(cl.coll), 6)::json AS hull,
                       ST_Y(ST_Centroid(cl.coll)) AS centre_lat, ST_X(ST_Centroid(cl.coll)) AS centre_lon,
                       n.officer_id, n.officer_name, n.base_location, round((n.distance_m / 1000.0)::numeric, 1) AS officer_distance_km
                FROM cl {NEAREST_OFFICER.format(pt='ST_Centroid(cl.coll)')}
                ORDER BY cl.size DESC""",
            params,
        )
        found = cur.fetchall()
        cur.execute(
            """SELECT count(*) AS total FROM facilities WHERE deployment_status = %s""", (status,)
        )
        total = cur.fetchone()["total"]
    clustered = sum(c["size"] for c in found)
    return {
        "status": status, "eps_km": eps_km, "min_points": min_points,
        "facilities_with_status": total, "clustered": clustered, "noise": total - clustered,
        "clusters": [
            {
                "cluster_id": c["cluster_id"], "size": c["size"], "districts": c["districts"],
                "facility_ids": c["facility_ids"], "hull": c["hull"],
                "centre": {"lat": c["centre_lat"], "lon": c["centre_lon"]},
                "nearest_officer": None if c["officer_id"] is None else {
                    "id": c["officer_id"], "name": c["officer_name"],
                    "base_location": c["base_location"], "distance_km": c["officer_distance_km"]},
            }
            for c in found
        ],
    }


@app.get("/analysis/no-connectivity", tags=["analysis"])
def no_connectivity(status: Optional[FilterStatus] = None):
    """Facilities recorded as having no internet and/or no power. NULL means 'not recorded'
    and is counted separately, never treated as 'no'."""
    with db.cursor() as cur:
        cur.execute(
            f"""SELECT {FACILITY_COLS}
                FROM facilities f LEFT JOIN support_officers o ON o.id = f.support_officer_id
                WHERE (f.has_internet IS FALSE OR f.has_power IS FALSE)
                  AND (%(status)s::text IS NULL OR f.deployment_status = %(status)s)
                ORDER BY f.district, f.name""",
            {"status": status},
        )
        rows = cur.fetchall()
        cur.execute(
            """SELECT count(*) FILTER (WHERE has_internet IS FALSE AND has_power IS FALSE) AS neither,
                      count(*) FILTER (WHERE has_internet IS FALSE AND has_power IS NOT FALSE) AS no_internet_only,
                      count(*) FILTER (WHERE has_power IS FALSE AND has_internet IS NOT FALSE) AS no_power_only,
                      count(*) FILTER (WHERE has_internet IS NULL OR has_power IS NULL) AS not_recorded
               FROM facilities
               WHERE (%(status)s::text IS NULL OR deployment_status = %(status)s)""",
            {"status": status},
        )
        counts = cur.fetchone()
    return feature_collection(rows, count=len(rows), summary=counts)


@app.get("/analysis/far-from-officer", tags=["analysis"])
def far_from_officer(km: float = Query(default=100, gt=0, le=1000)):
    """Facilities further than `km` kilometres from ANY support officer (true distance in metres).
    Returns an empty result with a note while no officers are loaded."""
    with db.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM support_officers")
        if cur.fetchone()["n"] == 0:
            return feature_collection([], count=0, km=km, by_district={},
                                      note="No support officers are loaded yet.")
        cur.execute(
            """SELECT f.id, f.facility_code, f.name, f.district, f.deployment_status,
                      d.officer_name, round((d.dist_m / 1000.0)::numeric, 1) AS distance_km,
                      ST_AsGeoJSON(f.geom, 6)::json AS geometry
               FROM facilities f
               CROSS JOIN LATERAL (
                   SELECT o.name AS officer_name, ST_Distance(o.geom::geography, f.geom::geography) AS dist_m
                   FROM support_officers o ORDER BY dist_m LIMIT 1
               ) d
               WHERE d.dist_m > %s
               ORDER BY d.dist_m DESC""",
            (km * 1000.0,),
        )
        rows = cur.fetchall()
    by_district = {}
    for r in rows:
        by_district[r["district"]] = by_district.get(r["district"], 0) + 1
    return feature_collection(rows, count=len(rows), km=km, by_district=by_district)


@app.get("/reports/missing-coordinates", tags=["analysis"])
def missing_coordinates():
    """Records that cannot be placed on the map or whose placement looks wrong."""
    with db.cursor() as cur:
        cur.execute(
            """SELECT id AS uid, name, parentname FROM orgunits_raw WHERE geom IS NULL
               ORDER BY parentname, name"""
        )
        no_geometry = cur.fetchall()
        cur.execute(
            """SELECT o.id AS uid, o.name, o.parentname FROM orgunits_raw o
               WHERE NOT EXISTS (SELECT 1 FROM facilities f WHERE f.facility_code = o.id)
               ORDER BY o.parentname, o.name"""
        )
        not_in_facilities = cur.fetchall()
        cur.execute(
            """SELECT row_id, facility_name, district FROM tracker_raw
               WHERE facility_id IS NULL ORDER BY district, facility_name"""
        )
        unmatched = cur.fetchall()
        cur.execute(
            f"""SELECT f.id, f.facility_code, f.name, f.district,
                       round((ST_Distance(f.geom::geography, d.geom::geography) / 1000.0)::numeric, 1) AS km_from_district
                FROM facilities f JOIN districts_hdx d ON d.name = {DISTRICT_POLYGON}
                WHERE NOT ST_Intersects(d.geom, f.geom)
                ORDER BY km_from_district DESC"""
        )
        outside = cur.fetchall()
    return {
        "org_units_without_coordinates": no_geometry,
        "org_units_not_in_facilities": not_in_facilities,
        "tracker_rows_without_a_facility": unmatched,
        "facilities_outside_their_district_polygon": outside,
        "counts": {
            "org_units_without_coordinates": len(no_geometry),
            "org_units_not_in_facilities": len(not_in_facilities),
            "tracker_rows_without_a_facility": len(unmatched),
            "facilities_outside_their_district_polygon": len(outside),
        },
    }


app.mount("/static", StaticFiles(directory=FRONTEND, check_dir=False), name="static")
