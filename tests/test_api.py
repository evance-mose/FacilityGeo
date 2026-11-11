"""API tests against the local database (needs the .env / DB_* settings).

    .venv/bin/pip install -r requirements-dev.txt
    .venv/bin/pytest -q

The write tests create one test facility and put everything back afterwards.
"""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

TEST_CODE = "TEST_API_001"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # opens the connection pool
        _cleanup()
        yield c
        _cleanup()


def _cleanup():
    with db.cursor(commit=True) as cur:
        cur.execute("DELETE FROM facilities WHERE facility_code = %s", (TEST_CODE,))


def valid_body(**over):
    body = {"facility_code": TEST_CODE, "name": "API Test Clinic", "district": "Zomba",
            "latitude": -15.386, "longitude": 35.319}
    body.update(over)
    return body


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_facilities_filters(client):
    r = client.get("/facilities", params={"status": "live"})
    assert r.status_code == 200
    assert all(f["properties"]["deployment_status"] == "live" for f in r.json()["features"])
    r = client.get("/facilities", params={"status": "not_in_tracker", "district": "Zomba"})
    assert r.status_code == 200
    feats = r.json()["features"]
    assert feats and all(f["properties"]["deployment_status"] == "not_in_tracker" for f in feats)
    assert all(f["properties"]["district"] == "Zomba" for f in feats)


@pytest.mark.parametrize("params", [{"status": "bogus"}, {"limit": 0}, {"limit": 999999}])
def test_facilities_rejects_bad_filters(client, params):
    assert client.get("/facilities", params=params).status_code == 422


@pytest.mark.parametrize("lat,lon", [(51.5, -0.1), (35.3, -15.4), (-15.4, 35.3 + 10), (0, 0)])
def test_post_rejects_coordinates_outside_malawi(client, lat, lon):
    r = client.post("/facilities", json=valid_body(latitude=lat, longitude=lon))
    assert r.status_code == 422


def test_post_rejects_unsafe_code_and_unknown_district(client):
    assert client.post("/facilities", json=valid_body(facility_code="x'; DROP TABLE facilities;--")).status_code == 422
    assert client.post("/facilities", json=valid_body(district="Atlantis")).status_code == 422
    assert client.post("/facilities", json=valid_body(deployment_status="done")).status_code == 422


def test_create_update_and_duplicate(client):
    r = client.post("/facilities", json=valid_body())
    assert r.status_code == 201, r.text
    created = r.json()["facility"]
    fid = created["id"]
    assert created["properties"]["support_officer"]            # nearest officer assigned
    assert created["geometry"]["coordinates"] == [35.319, -15.386]  # lon first

    assert client.post("/facilities", json=valid_body()).status_code == 409  # duplicate code

    r = client.patch(f"/facilities/{fid}/status", json={"deployment_status": "live"})
    assert r.status_code == 200 and r.json()["go_live_date"] is not None
    r = client.patch(f"/facilities/{fid}/status", json={"deployment_status": "not_started"})
    assert r.json()["go_live_date"] is None
    assert client.patch(f"/facilities/{fid}/status", json={"deployment_status": "bogus"}).status_code == 422
    assert client.patch("/facilities/999999999/status", json={"deployment_status": "live"}).status_code == 404


def test_stats_add_up(client):
    s = client.get("/stats/summary").json()
    assert s["live"] + s["in_progress"] + s["not_started"] + s["not_in_tracker"] == s["facilities"]
    assert s["tracked"] == s["facilities"] - s["not_in_tracker"]
    assert s["pct_live"] is None or 0 <= float(s["pct_live"]) <= 100
    d = client.get("/stats/districts", params={"sort": "pct_live_asc"}).json()
    assert sum(x["total"] for x in d) == s["facilities"]
    # % live is of tracked facilities; districts with none tracked (NULL) come last
    assert d == sorted(d, key=lambda x: (x["pct_live"] is None, float(x["pct_live"] or 0), x["district"]))
    assert all(x["tracked"] == x["total"] - x["not_in_tracker"] for x in d)
    assert client.get("/stats/districts", params={"sort": "name;DROP TABLE facilities"}).status_code == 422


def test_nearest_officer_matches_assignment(client):
    fid = client.get("/facilities", params={"limit": 1}).json()["features"][0]["id"]
    r = client.get("/analysis/nearest-officer", params={"facility_id": fid})
    assert r.status_code == 200
    body = r.json()
    assert body["matches_assigned_officer"] is True
    assert body["line"]["type"] == "LineString" and body["distance_m"] > 0
    assert client.get("/analysis/nearest-officer", params={"facility_id": 999999999}).status_code == 404


def test_within_radius_is_in_metres(client):
    r = client.get("/analysis/within-radius", params={"lat": -13.9626, "lon": 33.7741, "radius_km": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert all(f["properties"]["distance_m"] <= 10_000 for f in body["features"])
    assert client.get("/analysis/within-radius", params={"lat": 10, "lon": 33}).status_code == 422


def test_clusters_report_officer_and_hull(client):
    r = client.get("/analysis/clusters", params={"eps_km": 15, "min_points": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["clusters"] and body["clustered"] + body["noise"] == body["facilities_with_status"]
    first = body["clusters"][0]
    assert first["nearest_officer"]["name"] and first["hull"]["type"] in ("Polygon", "LineString", "Point")
    assert client.get("/analysis/clusters", params={"eps_km": 0}).status_code == 422


def test_extra_analysis_endpoints(client):
    nc = client.get("/analysis/no-connectivity").json()
    # The real tracker has no internet / power columns, so this can legitimately be empty.
    assert nc["count"] == len(nc["features"])
    far = client.get("/analysis/far-from-officer", params={"km": 100}).json()
    assert all(f["properties"]["distance_km"] > 100 for f in far["features"])
    rep = client.get("/reports/missing-coordinates").json()
    assert set(rep["counts"]) == {"org_units_without_coordinates", "org_units_not_in_facilities",
                                  "tracker_rows_without_a_facility", "facilities_outside_their_district_polygon"}
    assert len(client.get("/districts").json()["features"]) == 28
