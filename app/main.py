from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
