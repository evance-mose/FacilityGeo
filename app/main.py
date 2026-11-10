import json
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.database import engine, get_db
from app.models import HealthFacility, SupportOfficer
from app.spatial import (
    CLUSTER_SQL,
    DISTRICT_SUMMARY_SQL,
    ENSURE_DISTRICT_GEOM_SQL,
    NEAREST_OFFICER_SQL,
    SUMMARY_SQL,
    WITHIN_20KM_SQL,
    rows,
    visit_route,
)

app = FastAPI(
    title="FacilityGeo",
    description="Spatial deployment monitoring for health facilities in Malawi",
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
def prepare_spatial_layers():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgrouting"))
            conn.commit()
        except Exception:
            conn.rollback()
        conn.execute(ENSURE_DISTRICT_GEOM_SQL)
        conn.commit()


@app.get("/", response_class=HTMLResponse)
def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/api")
def api_root():
    return {
        "name": "FacilityGeo",
        "stack": ["PostgreSQL", "PostGIS", "FastAPI", "Leaflet"],
        "methods": ["ST_DWithin", "KNN <->", "ST_Contains", "ST_ClusterDBSCAN", "pgr_TSP"],
    }


@app.get("/api/summary")
def summary(db: Session = Depends(get_db)):
    data = rows(db, SUMMARY_SQL)[0]
    return {key: int(value) for key, value in data.items()}


@app.get("/api/districts")
def districts(db: Session = Depends(get_db)):
    table = []
    features = []
    for row in rows(db, DISTRICT_SUMMARY_SQL):
        item = {
            "id": int(row["id"]),
            "district": row["district"],
            "region": row["region"],
            "facilities": int(row["facilities"] or 0),
            "live": int(row["live"] or 0),
            "in_progress": int(row["in_progress"] or 0),
            "not_started": int(row["not_started"] or 0),
            "blocked": int(row["blocked"] or 0),
            "unserved_by_trained_staff": int(row["unserved_by_trained_staff"] or 0),
            "remote_or_no_utilities": int(row["remote_or_no_utilities"] or 0),
        }
        table.append(item)
        if row["geojson"]:
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(row["geojson"]),
                    "properties": item,
                }
            )
    return {"districts": table, "geojson": {"type": "FeatureCollection", "features": features}}


@app.get("/api/facilities.geojson")
def facilities_geojson(db: Session = Depends(get_db)):
    nearest = {row["facility_id"]: row for row in rows(db, NEAREST_OFFICER_SQL)}
    facilities = db.query(HealthFacility).options(joinedload(HealthFacility.district)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [facility.longitude, facility.latitude]},
                "properties": {
                    "id": facility.id,
                    "code": facility.code,
                    "name": facility.name,
                    "facility_type": facility.facility_type,
                    "mahis_status": facility.mahis_status,
                    "has_internet": facility.has_internet,
                    "has_power": facility.has_power,
                    "has_trained_staff": facility.has_trained_staff,
                    "is_remote": (not facility.has_internet) or (not facility.has_power),
                    "district": facility.district.name if facility.district else None,
                    "region": facility.district.region if facility.district else None,
                    "nearest_officer": (nearest.get(facility.id) or {}).get("officer_name"),
                    "nearest_officer_id": (nearest.get(facility.id) or {}).get("officer_id"),
                    "nearest_officer_km": float((nearest.get(facility.id) or {}).get("km") or 0),
                    "officer_lng": (nearest.get(facility.id) or {}).get("officer_lng"),
                    "officer_lat": (nearest.get(facility.id) or {}).get("officer_lat"),
                },
            }
            for facility in facilities
        ],
    }


@app.get("/api/officers.geojson")
def officers_geojson(db: Session = Depends(get_db)):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [officer.longitude, officer.latitude]},
                "properties": {"id": officer.id, "name": officer.name},
            }
            for officer in db.query(SupportOfficer).all()
        ],
    }


@app.get("/api/spatial/within-20km")
def within_20km(db: Session = Depends(get_db)):
    return rows(db, WITHIN_20KM_SQL)


@app.get("/api/spatial/clusters")
def clusters(db: Session = Depends(get_db)):
    result = []
    for row in rows(db, CLUSTER_SQL):
        result.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "mahis_status": row["mahis_status"],
                "cluster_id": None if row["cluster_id"] is None else int(row["cluster_id"]),
            }
        )
    return result


@app.get("/api/spatial/route")
def route(officer_id: int, db: Session = Depends(get_db)):
    return visit_route(db, officer_id)
