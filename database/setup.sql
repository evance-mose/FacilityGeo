-- FacilityGeo: rollout tables (local PostgreSQL + PostGIS)
-- Safe to re-run: every statement is IF NOT EXISTS. Works on an empty database.
-- Run as the database owner (or a superuser; CREATE EXTENSION needs it once):
--   psql -h localhost -d facilitygeo -f database/setup.sql
--
-- Roles and passwords are NOT created here (see README). The application role
-- `geo` is granted data access at the end if it exists.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- fuzzy name matching (tracker matching)

-- Support officers (fictional; filled in by database/assign_officers.sql).
CREATE TABLE IF NOT EXISTS support_officers (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    latitude      DOUBLE PRECISION NOT NULL,
    longitude     DOUBLE PRECISION NOT NULL,
    geom          GEOMETRY(Point, 4326) NOT NULL,
    base_location TEXT,
    is_simulated  BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS officers_geom_gix ON support_officers USING GIST (geom);

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
ALTER TABLE tracker_raw ADD COLUMN IF NOT EXISTS training      TEXT;
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
    -- not_in_tracker = the facility has no row in the rollout tracker (status unknown),
    -- which is different from a tracked facility that has not started.
    deployment_status  TEXT NOT NULL DEFAULT 'not_in_tracker'
        CHECK (deployment_status IN ('not_in_tracker', 'not_started', 'in_progress', 'live')),
    training_status    TEXT CHECK (training_status IN ('not_started', 'in_progress', 'done')),  -- end-user training; NULL = not recorded
    go_live_date       DATE,
    devices_installed  INTEGER CHECK (devices_installed >= 0),
    staff_trained      INTEGER CHECK (staff_trained >= 0),
    has_internet       BOOLEAN,             -- NULL = not recorded yet
    has_power          BOOLEAN,             -- NULL = not recorded yet
    support_officer_id INTEGER REFERENCES support_officers (id),
    match_method       TEXT,                -- code | exact_name | fuzzy_name | manual
    geom               GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS facilities_gix ON facilities USING GIST (geom);
-- Lets ST_DWithin(geom::geography, ...) (radius searches, metres) use an index.
CREATE INDEX IF NOT EXISTS facilities_geog_gix ON facilities USING GIST ((geom::geography));
-- Older databases: add training_status and allow the 'not_in_tracker' status.
ALTER TABLE facilities ADD COLUMN IF NOT EXISTS training_status TEXT
    CHECK (training_status IN ('not_started', 'in_progress', 'done'));
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'facilities'::regclass AND contype = 'c'
                     AND conname = 'facilities_deployment_status_check'
                     AND pg_get_constraintdef(oid) LIKE '%not_in_tracker%') THEN
        ALTER TABLE facilities DROP CONSTRAINT IF EXISTS facilities_deployment_status_check;
        ALTER TABLE facilities ADD CONSTRAINT facilities_deployment_status_check
            CHECK (deployment_status IN ('not_in_tracker', 'not_started', 'in_progress', 'live'));
    END IF;
END $$;
ALTER TABLE facilities ALTER COLUMN deployment_status SET DEFAULT 'not_in_tracker';
CREATE INDEX IF NOT EXISTS facilities_district_idx ON facilities (district);
CREATE INDEX IF NOT EXISTS facilities_status_idx ON facilities (deployment_status);
CREATE INDEX IF NOT EXISTS facilities_officer_idx ON facilities (support_officer_id);

-- HDX district polygons, used for drawing and for the "inside its district"
-- check. One row per HDX district (28); Mzimba is a single polygon here while
-- DHIS2 splits it into North and South.
CREATE TABLE IF NOT EXISTS districts_hdx (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE,
    region  TEXT,
    geom    GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS districts_hdx_gix ON districts_hdx USING GIST (geom);

-- Older databases created support_officers without these two columns.
ALTER TABLE support_officers ADD COLUMN IF NOT EXISTS base_location TEXT;
ALTER TABLE support_officers ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN NOT NULL DEFAULT TRUE;

-- Application role `geo`: data access only, no schema changes. Skipped if the
-- role has not been created yet.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'geo') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON
            orgunits_raw, tracker_raw, facilities, districts_hdx, support_officers TO geo;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO geo;
    END IF;
END $$;
