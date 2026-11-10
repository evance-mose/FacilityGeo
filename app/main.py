from fastapi import FastAPI

app = FastAPI(title="FacilityGeo")


@app.get("/")
def root():
    return {"name": "FacilityGeo"}
