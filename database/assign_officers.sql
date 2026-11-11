-- Simulated support officers and nearest-officer assignment.
--   psql -h localhost -d facilitygeo -f database/assign_officers.sql    (run from FacilityGeo/)
-- Run after database/setup.sql. Safe to re-run.
--
-- The officers are FICTIONAL (is_simulated = TRUE), based at four district
-- HQ towns. Names are made up; coordinates are the towns, not real staff.
-- Longitude comes first in ST_MakePoint(lon, lat).

\set ON_ERROR_STOP on

-- The three sample officers keep their ids; they just get a base_location.
UPDATE support_officers SET base_location = 'Lilongwe (district HQ)'  WHERE name = 'Thandiwe Banda';
UPDATE support_officers SET base_location = 'Blantyre (district HQ)'  WHERE name = 'Chikondi Phiri';
UPDATE support_officers SET base_location = 'Mzuzu (Mzimba North HQ)' WHERE name = 'Mwai Nyirenda';

-- A fourth officer in Zomba (district_id 5 = Zomba in the sample districts table).
INSERT INTO support_officers (name, district_id, latitude, longitude, geom, base_location, is_simulated)
SELECT 'Yamikani Chirwa', 5, -15.386, 35.319, ST_SetSRID(ST_MakePoint(35.319, -15.386), 4326),
       'Zomba (district HQ)', TRUE
WHERE NOT EXISTS (SELECT 1 FROM support_officers WHERE name = 'Yamikani Chirwa');

-- Assign every facility to its nearest officer. The <-> KNN operator ranks by
-- degrees (index-assisted, slightly wrong east-west), so it only picks the 3
-- candidates; the final choice is by true distance in metres (::geography).
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

\echo '== Officers =='
SELECT id, name, base_location, is_simulated, round(ST_X(geom)::numeric, 3) AS lon, round(ST_Y(geom)::numeric, 3) AS lat
FROM support_officers ORDER BY id;

\echo '== Facilities per officer, with distance to the assigned officer (km) =='
SELECT o.name, count(*) AS facilities,
       round((avg(ST_Distance(f.geom::geography, o.geom::geography)) / 1000)::numeric, 1) AS avg_km,
       round((max(ST_Distance(f.geom::geography, o.geom::geography)) / 1000)::numeric, 1) AS max_km
FROM facilities f JOIN support_officers o ON o.id = f.support_officer_id
GROUP BY o.name ORDER BY facilities DESC;

\echo '== Unassigned facilities (expect 0) =='
SELECT count(*) FROM facilities WHERE support_officer_id IS NULL;
