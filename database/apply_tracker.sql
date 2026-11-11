-- Copy matched tracker data into facilities (the table the API reads).
--   psql -h localhost -d facilitygeo -f database/apply_tracker.sql      (run from FacilityGeo/)
-- Run after database/match_tracker.sql.
--
-- The tracker is the source of truth: rollout columns are reset first, so
-- re-running replaces anything changed since (including status set through
-- the API PATCH endpoint). Facilities with no tracker row become
-- 'not_in_tracker' (status unknown), which is not the same as 'not_started'.
-- Values that cannot be parsed become NULL and are counted in the report.

\set ON_ERROR_STOP on

CREATE OR REPLACE FUNCTION pg_temp.to_status(s TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN lower(btrim(s)) ~ '(not\s*started|not\s*live|pending|planned|not yet)|^no$' THEN 'not_started'
        WHEN lower(btrim(s)) ~ '(progress|ongoing|install|partial)'            THEN 'in_progress'
        WHEN lower(btrim(s)) ~ '(live|complete|done|deployed)'                 THEN 'live'
    END
$$;
CREATE OR REPLACE FUNCTION pg_temp.to_training(s TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN lower(btrim(s)) ~ '(not\s*started|not\s*done|pending|not yet)|^no$' THEN 'not_started'
        WHEN lower(btrim(s)) ~ '(progress|ongoing|partial)'                      THEN 'in_progress'
        WHEN lower(btrim(s)) ~ '(done|complete|trained)|^yes$'                   THEN 'done'
    END
$$;
CREATE OR REPLACE FUNCTION pg_temp.to_date(s TEXT) RETURNS DATE LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN btrim(s) ~ '^\d{4}-\d{2}-\d{2}$' THEN to_date(btrim(s), 'YYYY-MM-DD')
        WHEN btrim(s) ~ '^\d{1,2}/\d{1,2}/\d{4}$' THEN to_date(btrim(s), 'DD/MM/YYYY')
    END
$$;
CREATE OR REPLACE FUNCTION pg_temp.to_int(s TEXT) RETURNS INTEGER LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN btrim(s) ~ '^\d{1,6}$' THEN btrim(s)::integer END
$$;
CREATE OR REPLACE FUNCTION pg_temp.to_bool(s TEXT) RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN lower(btrim(s)) IN ('yes', 'y', 'true', '1', 'available', 'stable') THEN TRUE
        WHEN lower(btrim(s)) IN ('no', 'n', 'false', '0', 'none', 'unavailable') THEN FALSE
    END
$$;

-- Reset rollout columns (support_officer_id is assigned separately, task 4).
UPDATE facilities
SET deployment_status = 'not_in_tracker', training_status = NULL, go_live_date = NULL,
    devices_installed = NULL, staff_trained = NULL, has_internet = NULL, has_power = NULL,
    match_method = NULL;

-- One tracker row per facility: the latest row wins.
UPDATE facilities f
SET deployment_status = coalesce(pg_temp.to_status(t.status), 'not_started'),
    training_status   = pg_temp.to_training(t.training),
    go_live_date      = pg_temp.to_date(t.go_live_date),
    devices_installed = pg_temp.to_int(t.devices),
    staff_trained     = pg_temp.to_int(t.staff_trained),
    has_internet      = pg_temp.to_bool(t.internet),
    has_power         = pg_temp.to_bool(t.power),
    match_method      = t.match_method
FROM (
    SELECT DISTINCT ON (facility_id) *
    FROM tracker_raw WHERE facility_id IS NOT NULL
    ORDER BY facility_id, row_id DESC
) t
WHERE f.facility_code = t.facility_id;

\echo '== Facilities by deployment status =='
SELECT deployment_status, count(*) AS facilities,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM facilities GROUP BY 1 ORDER BY 1;

\echo '== Matched facilities by method (NULL = no tracker row) =='
SELECT coalesce(match_method, 'no tracker row') AS method, count(*) FROM facilities GROUP BY 1 ORDER BY 2 DESC;

\echo '== Tracker values that could not be parsed (left NULL / defaulted) =='
SELECT
  count(*) FILTER (WHERE pg_temp.to_status(status) IS NULL)                         AS bad_status,
  count(*) FILTER (WHERE training IS NOT NULL AND pg_temp.to_training(training) IS NULL) AS bad_training,
  count(*) FILTER (WHERE go_live_date IS NOT NULL AND pg_temp.to_date(go_live_date) IS NULL) AS bad_date,
  count(*) FILTER (WHERE devices IS NOT NULL AND pg_temp.to_int(devices) IS NULL)   AS bad_devices,
  count(*) FILTER (WHERE internet IS NOT NULL AND pg_temp.to_bool(internet) IS NULL) AS bad_internet,
  count(*) FILTER (WHERE power IS NOT NULL AND pg_temp.to_bool(power) IS NULL)      AS bad_power
FROM tracker_raw WHERE facility_id IS NOT NULL;
