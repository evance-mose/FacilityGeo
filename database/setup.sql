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

-- Staging: the rollout tracker CSV. All text on purpose; cleaned when
-- facilities is updated. scripts/load_tracker.py maps the CSV headers onto
-- these columns. facility_id / match_method are filled in during matching
-- (database/match_tracker.sql); facility_id holds the DHIS2 UID.
CREATE TABLE IF NOT EXISTS tracker_raw (
    row_id          SERIAL PRIMARY KEY,
    facility_name   TEXT,
    district        TEXT,
    facility_code   TEXT,
    status          TEXT,
    go_live_date    TEXT,
    devices         TEXT,
    staff_trained   TEXT,
    internet        TEXT,
    power           TEXT,
    facility_id     TEXT,
    match_method    TEXT
);
-- Older databases created tracker_raw with only the two matching columns.
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS facility_name TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS district      TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS facility_code TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS status        TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS go_live_date  TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS devices       TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS staff_trained TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS internet      TEXT;
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS power         TEXT;

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

-- HDX district polygons, used for drawing and for the "inside its district"
-- check. Separate from the sample `districts` table, which other sample
-- tables reference. One row per HDX district (28); Mzimba is a single polygon
-- here while DHIS2 splits it into North and South.
CREATE TABLE IF NOT EXISTS districts_hdx (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    region  TEXT,
    geom    GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS districts_hdx_gix ON districts_hdx USING GIST (geom);

-- Application role `geo`: data access only, no schema changes. Skipped if the
-- role has not been created yet.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'geo') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON
            orgunits_raw, tracker_raw, facilities, districts_hdx TO geo;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO geo;
    END IF;
END $$;
