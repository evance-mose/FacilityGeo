-- FacilityGeo: data quality checks (read-only, safe to re-run).
--   psql -h localhost -d facilitygeo -f database/checks.sql

\echo '== 1. Facilities per district (DHIS2 district) =='
SELECT district, COUNT(*) AS facilities
FROM facilities GROUP BY district ORDER BY district;

\echo '== 2. Missing or impossible coordinates (expect 0 rows) =='
SELECT facility_code, name, district
FROM facilities
WHERE geom IS NULL
   OR ST_IsEmpty(geom)
   OR (ST_X(geom) = 0 AND ST_Y(geom) = 0)
   OR NOT (ST_X(geom) BETWEEN 32.5 AND 36.0 AND ST_Y(geom) BETWEEN -17.2 AND -9.2);

\echo '== 3. Facilities outside their own district polygon =='
-- DHIS2 splits Mzimba into North/South; the HDX file has one Mzimba polygon.
-- distance_m = how far the point is from its own district polygon (geography).
WITH f AS (
    SELECT f.*, CASE WHEN f.district LIKE 'Mzimba %' THEN 'Mzimba' ELSE f.district END AS poly_name
    FROM facilities f
)
SELECT f.facility_code, f.name, f.district,
       round(ST_X(f.geom)::numeric, 4) AS lon, round(ST_Y(f.geom)::numeric, 4) AS lat,
       round(ST_Distance(f.geom::geography, d.geom::geography)::numeric) AS distance_m,
       (SELECT string_agg(o.name, ', ') FROM districts_hdx o
         WHERE ST_Intersects(o.geom, f.geom)) AS inside_polygon_of
FROM f
LEFT JOIN districts_hdx d ON d.name = f.poly_name
WHERE d.id IS NULL OR NOT ST_Intersects(d.geom, f.geom)
ORDER BY distance_m DESC NULLS FIRST;

\echo '== 4a. Same name in the same district (duplicates) =='
SELECT f.name, f.district, COUNT(*) AS n, string_agg(f.facility_code, ', ' ORDER BY f.facility_code) AS codes,
       COUNT(DISTINCT f.geom) AS distinct_locations
FROM facilities f
GROUP BY f.name, f.district HAVING COUNT(*) > 1;

\echo '== 4b. Different names at exactly the same location =='
SELECT ST_AsText(geom) AS location, COUNT(*) AS n, string_agg(name || ' [' || district || ']', ' | ' ORDER BY name) AS facilities
FROM facilities
GROUP BY geom HAVING COUNT(*) > 1
ORDER BY n DESC, location;

\echo '== 4c. Same name in different districts (informational) =='
SELECT name, COUNT(*) AS n, string_agg(district, ', ' ORDER BY district) AS districts
FROM facilities GROUP BY name HAVING COUNT(DISTINCT district) > 1 ORDER BY n DESC, name;

\echo '== 5. Districts with polygons but no facilities, and the reverse (expect none) =='
SELECT d.name AS polygon_without_facilities
FROM districts_hdx d
WHERE NOT EXISTS (SELECT 1 FROM facilities f
                  WHERE (CASE WHEN f.district LIKE 'Mzimba %' THEN 'Mzimba' ELSE f.district END) = d.name);
SELECT DISTINCT f.district AS facility_district_without_polygon
FROM facilities f
WHERE NOT EXISTS (SELECT 1 FROM districts_hdx d
                  WHERE d.name = (CASE WHEN f.district LIKE 'Mzimba %' THEN 'Mzimba' ELSE f.district END));
