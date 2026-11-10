-- FacilityGeo spatial questions (sample data must be loaded)

-- 1. Facilities within 20 km of each support officer
SELECT o.name AS officer, f.name AS facility, f.mahis_status,
       ROUND((ST_Distance(o.geom::geography, f.geom::geography) / 1000)::numeric, 1) AS km
FROM support_officers o
JOIN health_facilities f ON ST_DWithin(o.geom::geography, f.geom::geography, 20000)
ORDER BY o.name, km;

-- 2. Nearest support officer for each facility (KNN)
SELECT f.name AS facility, o.name AS nearest_officer,
       ROUND((ST_Distance(f.geom::geography, o.geom::geography) / 1000)::numeric, 1) AS km
FROM health_facilities f
CROSS JOIN LATERAL (
    SELECT name, geom FROM support_officers ORDER BY f.geom <-> geom LIMIT 1
) o;

-- 3. Live facilities per district
SELECT d.name, d.region,
       COUNT(*) FILTER (WHERE f.mahis_status = 'live') AS live,
       COUNT(*) AS total
FROM districts d
JOIN health_facilities f ON ST_Contains(d.geom, f.geom)
GROUP BY d.name, d.region
ORDER BY live ASC;

-- 4. Clusters of undeployed facilities
SELECT id, name, mahis_status,
       ST_ClusterDBSCAN(geom, eps := 0.5, minpoints := 2) OVER () AS cluster_id
FROM health_facilities
WHERE mahis_status <> 'live';

-- 5. Visit order: see FastAPI /api/spatial/route?officer_id=1 (pgr_TSP)
