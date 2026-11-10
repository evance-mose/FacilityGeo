from fastapi import FastAPI

app = FastAPI(
    title="FacilityGeo",
    description="A Spatial Deployment Monitoring System for Health Facilities in Malawi",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "FacilityGeo",
        "status": "ok",
        "message": "Spatial deployment monitoring for health facilities in Malawi",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
