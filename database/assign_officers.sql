-- Assign each facility to its nearest support officer.
--   psql -h localhost -d facilitygeo -f database/assign_officers.sql    (run from FacilityGeo/)
-- Run after database/setup.sql and after real officers are in support_officers.
-- Safe to re-run.
--
-- NO officers are shipped or invented. support_officers starts empty, and with
-- no rows this script leaves every facility unassigned. To enable the officer
-- features, insert real officers (longitude comes first in ST_MakePoint):
--
--   INSERT INTO support_officers (name, latitude, longitude, geom, base_location, is_simulated)
--   VALUES ('Real Name', -15.78, 35.00, ST_SetSRID(ST_MakePoint(35.00, -15.78), 4326),
--           'Blantyre district office', FALSE);

\set ON_ERROR_STOP on

-- Start from scratch so removed officers never leave stale assignments.
UPDATE facilities SET support_officer_id = NULL WHERE support_officer_id IS NOT NULL;

-- The <-> KNN operator ranks by degrees (index-assisted, slightly wrong
-- east-west), so it only picks 3 candidates; the final choice is by true
-- distance in metres (::geography). With zero officers this updates nothing.
UPDATE facilities f
SET support_officer_id = n.officer_id
FROM (
    SELECT fa.id AS facility_id, o.id AS officer_id
    FROM facilities fa
    CROSS JOIN LATERAL (
        SELECT c.id
        FROM (SELECT id, geom FROM support_officers ORDER BY geom <-> fa.geom LIMIT 3) c
        ORDER BY ST_Distance(c.geom::geography, fa.geom::geography)
        LIMIT 1
    ) o
) n
WHERE f.id = n.facility_id;

\echo '== Officers loaded (0 means the officer features stay off) =='
SELECT count(*) AS officers FROM support_officers;

\echo '== Facilities per officer, with distance to the assigned officer (km) =='
SELECT o.name, count(*) AS facilities,
       round((avg(ST_Distance(f.geom::geography, o.geom::geography)) / 1000)::numeric, 1) AS avg_km,
       round((max(ST_Distance(f.geom::geography, o.geom::geography)) / 1000)::numeric, 1) AS max_km
FROM facilities f JOIN support_officers o ON o.id = f.support_officer_id
GROUP BY o.name ORDER BY facilities DESC;

\echo '== Facilities without an assigned officer =='
SELECT count(*) FROM facilities WHERE support_officer_id IS NULL;
