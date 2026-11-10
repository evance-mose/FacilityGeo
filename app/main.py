from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import HealthFacility, SupportOfficer

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

app = FastAPI(
    title="FacilityGeo",
    description="Spatial deployment monitoring for health facilities in Malawi",
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/api")
def api_root():
    return {"name": "FacilityGeo", "stack": ["PostgreSQL", "PostGIS", "FastAPI", "Leaflet"]}


@app.get("/api/facilities.geojson")
def facilities_geojson(db: Session = Depends(get_db)):
    nearest = {
        row["facility_id"]: row
        for row in db.execute(NEAREST_OFFICER_SQL).mappings()
    }
    rows = db.query(HealthFacility).options(joinedload(HealthFacility.district)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [facility.longitude, facility.latitude],
                },
                "properties": {
                    "code": facility.code,
                    "name": facility.name,
                    "facility_type": facility.facility_type,
                    "mahis_status": facility.mahis_status,
                    "has_internet": facility.has_internet,
                    "has_power": facility.has_power,
                    "has_trained_staff": facility.has_trained_staff,
                    "district": facility.district.name if facility.district else None,
                    "region": facility.district.region if facility.district else None,
                    "nearest_officer": (nearest.get(facility.id) or {}).get("officer_name"),
                    "nearest_officer_km": float((nearest.get(facility.id) or {}).get("km") or 0),
                    "officer_lng": (nearest.get(facility.id) or {}).get("officer_lng"),
                    "officer_lat": (nearest.get(facility.id) or {}).get("officer_lat"),
                },
            }
            for facility in rows
        ],
    }


@app.get("/api/officers.geojson")
def officers_geojson(db: Session = Depends(get_db)):
    rows = db.query(SupportOfficer).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [officer.longitude, officer.latitude],
                },
                "properties": {"name": officer.name},
            }
            for officer in rows
        ],
    }
