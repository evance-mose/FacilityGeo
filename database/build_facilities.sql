-- Build/refresh facilities from the DHIS2 org units (orgunits_raw).
--   psql -h localhost -d facilitygeo -f database/build_facilities.sql
--
-- facility_code = DHIS2 UID.
-- district      = parentname with '-DHO' removed and hyphens turned into
--                 spaces ('Mzimba-North-DHO' -> 'Mzimba North'). This is the
--                 DHIS2 district, not a spatial join.
-- Only identity, district and location are written. Rollout columns
-- (status, dates, devices, internet/power, officer, match_method) are left
-- untouched, so re-running never overwrites tracker data (task 3).
-- Deployment status defaults to 'not_started' until the tracker is matched.

INSERT INTO facilities (facility_code, name, district, geom)
SELECT o.id,
       btrim(o.name),
       btrim(replace(regexp_replace(o.parentname, '-DHO\s*$', ''), '-', ' ')),
       o.geom
FROM orgunits_raw o
WHERE o.geom IS NOT NULL
  AND o.parentname IS NOT NULL
ON CONFLICT (facility_code) DO UPDATE
   SET name     = EXCLUDED.name,
       district = EXCLUDED.district,
       geom     = EXCLUDED.geom;

-- Quick report
SELECT COUNT(*) AS facilities,
       COUNT(DISTINCT district) AS districts,
       COUNT(*) FILTER (WHERE deployment_status = 'not_started') AS not_started
FROM facilities;
