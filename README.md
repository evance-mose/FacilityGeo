# FacilityGeo

A spatial deployment monitoring system for health facilities in Malawi.

MaHIS is being rolled out to many health facilities, but the deployment team has no spatial view of progress or support needs. Tracking lives in spreadsheets, so it is hard to answer location-based questions:

- Which facilities are not yet live, and where are they clustered?
- Which facilities are remote, with no internet or power, and need a different deployment approach?
- Which support officer is closest to each facility, and what is the most efficient route for a support visit?
- Which districts are falling behind, and which facilities are still unserved by trained staff?

**Stack:** PostgreSQL + PostGIS, FastAPI (Python), Leaflet

## Spatial methods

| Question | Method |
|---|---|
| Which facilities are within 20 km of each support officer? | `ST_DWithin` |
| Which facility is nearest to each support officer? | KNN (`<->`) |
| How many facilities are live per district? | `ST_Contains` + `GROUP BY` |
| Where are clusters of undeployed facilities? | `ST_ClusterDBSCAN` |
| What is the best order to visit facilities? | pgRouting `pgr_TSP` |

SQL examples: [`sql/spatial_queries.sql`](sql/spatial_queries.sql)

## Run

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

If the database already existed before sample data was added:

```bash
docker compose exec -T db psql -U facilitygeo -d facilitygeo < sql/seed.sql
```

If pgRouting is missing, recreate the database volume or keep using the greedy visit-order fallback:

```bash
docker compose down -v
docker compose up -d db
```

## Data issues you may run into

- Missing or swapped coordinates, or points outside Malawi
- Facility names that do not match the official registry
- Outdated tracking sheets
- Internet and power not recorded yet
- Approval delays, which is why this repo starts with sample data
