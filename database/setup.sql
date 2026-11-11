-- FacilityGeo: rollout tables (local PostgreSQL + PostGIS)
-- Safe to re-run: every statement is IF NOT EXISTS.
-- Run as a superuser (needed once for CREATE EXTENSION):
--   psql -h localhost -d facilitygeo -f database/setup.sql
--
-- NOTE: districts and support_officers already exist from the sample seed.
-- Later tasks extend them (base_location, HDX polygons); this file only adds
-- new objects. Roles and passwords are NOT created here (see README).

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy name matching (task 3)

-- Staging: DHIS2 org units exactly as exported (level 4 facilities).
-- No code column in the export: the DHIS2 UID is the id.
CREATE TABLE IF NOT EXISTS orgunits_raw (
    id          TEXT PRIMARY KEY,           -- DHIS2 UID
    name        TEXT NOT NULL,
    parentname  TEXT,                       -- e.g. 'Mangochi-DHO'
    level       INTEGER,
    geom        GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS orgunits_raw_geom_gix ON orgunits_raw USING GIST (geom);
CREATE INDEX IF NOT EXISTS orgunits_raw_name_trgm ON orgunits_raw USING GIN (name gin_trgm_ops);

-- Staging: the rollout tracker CSV. All text on purpose; cleaned in task 3.
-- facility_id / match_method are filled in during matching.
-- Columns are added when the CSV is loaded (header-driven), so only the
-- matching columns are fixed here.
CREATE TABLE IF NOT EXISTS tracker_raw (
    row_id        SERIAL PRIMARY KEY,
    facility_id   TEXT,
    match_method  TEXT
);

-- Clean table the API reads. facility_code = DHIS2 UID.
CREATE TABLE IF NOT EXISTS facilities (
    id                 SERIAL PRIMARY KEY,
    facility_code      TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    district           TEXT NOT NULL,       -- DHIS2 district, not a spatial join
    facility_type      TEXT,
    deployment_status  TEXT NOT NULL DEFAULT 'not_started'
        CHECK (deployment_status IN ('not_started', 'in_progress', 'live')),
    go_live_date       DATE,
    devices_installed  INTEGER CHECK (devices_installed >= 0),
    staff_trained      INTEGER CHECK (staff_trained >= 0),
    has_internet       BOOLEAN,             -- NULL = not recorded yet
    has_power          BOOLEAN,             -- NULL = not recorded yet
    support_officer_id INTEGER REFERENCES support_officers (id),
    match_method       TEXT,                -- code | exact_name | fuzzy_name | manual
    geom               GEOMETRY(Point, 4326) NOT NULL
);
-- Name is facilities_gix (not facilities_geom_gix): that name is already used
-- by the sample health_facilities table and IF NOT EXISTS would silently skip it.
CREATE INDEX IF NOT EXISTS facilities_gix ON facilities USING GIST (geom);
CREATE INDEX IF NOT EXISTS facilities_district_idx ON facilities (district);
CREATE INDEX IF NOT EXISTS facilities_status_idx ON facilities (deployment_status);
CREATE INDEX IF NOT EXISTS facilities_officer_idx ON facilities (support_officer_id);
