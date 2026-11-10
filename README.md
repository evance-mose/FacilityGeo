# FacilityGeo

A spatial deployment monitoring system for health facilities in Malawi.

## Run

```bash
cd FacilityGeo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and http://127.0.0.1:8000/docs
