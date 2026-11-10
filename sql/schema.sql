CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

CREATE TABLE districts (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(80) NOT NULL UNIQUE,
    region  VARCHAR(40) NOT NULL,
    geom    GEOMETRY(MultiPolygon, 4326)
);

CREATE TABLE health_facilities (
    id                SERIAL PRIMARY KEY,
    code              VARCHAR(32) NOT NULL UNIQUE,
    name              VARCHAR(160) NOT NULL,
    facility_type     VARCHAR(80) NOT NULL,
    district_id       INTEGER NOT NULL REFERENCES districts (id),
    latitude          DOUBLE PRECISION NOT NULL,
    longitude         DOUBLE PRECISION NOT NULL,
    geom              GEOMETRY(Point, 4326) NOT NULL,
    mahis_status      VARCHAR(32) NOT NULL DEFAULT 'not_started',
    has_internet      BOOLEAN NOT NULL DEFAULT FALSE,
    has_power         BOOLEAN NOT NULL DEFAULT FALSE,
    has_trained_staff BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE support_officers (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    district_id INTEGER REFERENCES districts (id),
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL,
    geom        GEOMETRY(Point, 4326) NOT NULL
);

CREATE TABLE deployment_events (
    id          SERIAL PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES health_facilities (id) ON DELETE CASCADE,
    status      VARCHAR(32) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX districts_geom_gix ON districts USING GIST (geom);
CREATE INDEX facilities_geom_gix ON health_facilities USING GIST (geom);
CREATE INDEX officers_geom_gix ON support_officers USING GIST (geom);
