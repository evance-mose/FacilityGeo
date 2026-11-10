from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import HealthFacility

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
                },
            }
            for facility in rows
        ],
    }
