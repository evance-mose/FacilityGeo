-- Match tracker_raw rows to facilities (DHIS2 org units).
--   psql -h localhost -d facilitygeo -f database/match_tracker.sql      (run from FacilityGeo/)
-- Run after: load_orgunits.py, build_facilities.sql, load_tracker.py.
-- Safe to re-run: it recomputes facility_id / match_method from scratch.
--
-- Order (a row is only matched once):
--   1. code        tracker code = DHIS2 UID
--   2. exact_name  same normalised name in a compatible district, and unambiguous
--   2b. core_name  same name once facility-type words are removed, unique in the district
--   3. fuzzy_name  pg_trgm similarity >= 0.55 with a clear winner (margin >= 0.10)
--   4. manual      database/manual_matches.sql (decisions made by hand)
-- Anything else stays unmatched and is listed in the review reports below.
-- District compatibility: equal names, or tracker 'Mzimba' vs DHIS2
-- 'Mzimba North' / 'Mzimba South'.

\set ON_ERROR_STOP on

-- Name normalisation: lower case, expand common abbreviations, drop punctuation.
CREATE OR REPLACE FUNCTION pg_temp.norm(t TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT btrim(regexp_replace(regexp_replace(
        regexp_replace(regexp_replace(regexp_replace(
            lower(coalesce(t, '')),
            '\yhc\y', 'health centre', 'g'),
            '\yhosp\y', 'hospital', 'g'),
            '\ydisp\y', 'dispensary', 'g'),
            '[^a-z0-9 ]', ' ', 'g'),
            '\s+', ' ', 'g'))
$$;

UPDATE tracker_raw SET facility_id = NULL, match_method = NULL;

CREATE TEMP TABLE t_n AS
SELECT row_id, pg_temp.norm(facility_name) AS nname, pg_temp.norm(district) AS ndist,
       btrim(facility_code) AS code
FROM tracker_raw;

CREATE TEMP TABLE f_n AS
SELECT facility_code, pg_temp.norm(name) AS nname, pg_temp.norm(district) AS ndist
FROM facilities;
CREATE INDEX ON f_n USING GIN (nname gin_trgm_ops);

-- 1. code
UPDATE tracker_raw t SET facility_id = f.facility_code, match_method = 'code'
FROM t_n JOIN facilities f ON f.facility_code = t_n.code
WHERE t.row_id = t_n.row_id;

-- 2. exact normalised name, only when exactly one facility fits and no other
--    tracker row competes for the same name + district.
UPDATE tracker_raw t SET facility_id = c.facility_code, match_method = 'exact_name'
FROM (
    SELECT tn.row_id, min(fn.facility_code) AS facility_code
    FROM t_n tn
    JOIN f_n fn ON fn.nname = tn.nname
               AND (fn.ndist = tn.ndist OR (tn.ndist = 'mzimba' AND fn.ndist LIKE 'mzimba %'))
    WHERE tn.row_id IN (SELECT row_id FROM tracker_raw WHERE facility_id IS NULL)
    GROUP BY tn.row_id
    HAVING count(*) = 1
) c
WHERE t.row_id = c.row_id
  AND c.facility_code NOT IN (SELECT facility_id FROM tracker_raw WHERE facility_id IS NOT NULL);

-- 2b. core name: the name without facility-type words ("Chabvala" vs
--     "Chabvala Health Centre"), spaces removed ("Gate way" vs "Gateway").
--     Accepted only when exactly one unmatched facility in the district has
--     that core and no other unmatched tracker row has it too.
--     DHIS2 often adds the district in brackets ("Bua Health Centre (Kasungu)"),
--     so a trailing district name is dropped too (d = normalised district).
CREATE OR REPLACE FUNCTION pg_temp.core(t TEXT, d TEXT) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT replace(btrim(regexp_replace(
        regexp_replace(regexp_replace(t, '\y' || d || '$', ' '),
            '\y(health|centre|center|dispensary|clinic|hospital|community|post|blm|mission|urban|rural)\y', ' ', 'g'),
        '\s+', ' ', 'g')), ' ', '')
$$;
UPDATE tracker_raw t SET facility_id = c.facility_code, match_method = 'core_name'
FROM (
    SELECT tn.row_id, min(fn.facility_code) AS facility_code
    FROM t_n tn
    JOIN f_n fn ON pg_temp.core(fn.nname, fn.ndist) = pg_temp.core(tn.nname, tn.ndist)
               AND pg_temp.core(tn.nname, tn.ndist) <> ''
               -- a tracker name that states a type must agree on hospital / not hospital
               AND (tn.nname !~ '\y(health|centre|center|dispensary|clinic|hospital|post)\y'
                    OR (tn.nname ~ '\yhospital\y') = (fn.nname ~ '\yhospital\y'))
               AND (fn.ndist = tn.ndist OR (tn.ndist = 'mzimba' AND fn.ndist LIKE 'mzimba %'))
    WHERE tn.row_id IN (SELECT row_id FROM tracker_raw WHERE facility_id IS NULL)
      AND fn.facility_code NOT IN (SELECT facility_id FROM tracker_raw WHERE facility_id IS NOT NULL)
      AND (SELECT count(*) FROM t_n o
           WHERE o.row_id IN (SELECT row_id FROM tracker_raw WHERE facility_id IS NULL)
             AND pg_temp.core(o.nname, o.ndist) = pg_temp.core(tn.nname, tn.ndist) AND o.ndist = tn.ndist) = 1
    GROUP BY tn.row_id
    HAVING count(*) = 1
) c
WHERE t.row_id = c.row_id;

-- 3. fuzzy: best candidate among facilities not yet matched, same district.
CREATE TEMP TABLE fuzzy_c AS
    SELECT tn.row_id, b.facility_code, b.sim, b.sim - coalesce(b.sim2, 0) AS margin
    FROM t_n tn
    CROSS JOIN LATERAL (
        SELECT x.facility_code, x.sim, lead(x.sim) OVER (ORDER BY x.sim DESC) AS sim2
        FROM (
            SELECT fn.facility_code, similarity(fn.nname, tn.nname) AS sim
            FROM f_n fn
            WHERE (fn.ndist = tn.ndist OR (tn.ndist = 'mzimba' AND fn.ndist LIKE 'mzimba %'))
              AND fn.facility_code NOT IN (SELECT facility_id FROM tracker_raw WHERE facility_id IS NOT NULL)
            ORDER BY sim DESC
            LIMIT 2
        ) x
        ORDER BY x.sim DESC
        LIMIT 1
    ) b
    WHERE tn.row_id IN (SELECT row_id FROM tracker_raw WHERE facility_id IS NULL)
      AND b.sim >= 0.55
      AND b.sim - coalesce(b.sim2, 0) >= 0.10;

-- if two tracker rows picked the same facility, neither is accepted (manual review)
UPDATE tracker_raw t SET facility_id = c.facility_code, match_method = 'fuzzy_name'
FROM fuzzy_c c
WHERE t.row_id = c.row_id
  AND (SELECT count(*) FROM fuzzy_c d WHERE d.facility_code = c.facility_code) = 1;

-- 4. manual decisions
\ir manual_matches.sql

-- ---------------------------------------------------------------- reports
\echo
\echo '== Match summary =='
SELECT coalesce(match_method, 'UNMATCHED') AS method, count(*) AS tracker_rows
FROM tracker_raw GROUP BY 1 ORDER BY 2 DESC;

\echo '== Two tracker rows matched to the same facility (latest row wins when applied) =='
SELECT facility_id, count(*) AS rows, string_agg(facility_name || ' [' || row_id || ']', ' | ') AS tracker_names
FROM tracker_raw WHERE facility_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1;

\echo '== Core-name and fuzzy matches to eyeball (lowest similarity first) =='
SELECT t.row_id, t.facility_name AS tracker_name, t.district AS tracker_district,
       f.name AS matched_facility, f.district AS matched_district,
       round(similarity(pg_temp.norm(t.facility_name), pg_temp.norm(f.name))::numeric, 2) AS similarity
FROM tracker_raw t JOIN facilities f ON f.facility_code = t.facility_id
WHERE t.match_method IN ('core_name', 'fuzzy_name')
ORDER BY t.match_method, similarity LIMIT 60;

\echo '== UNMATCHED tracker rows: review by hand, then add them to database/manual_matches.sql =='
SELECT t.row_id, t.facility_name, t.district,
       (SELECT f.name || ' [' || f.district || '] ' || round(similarity(pg_temp.norm(t.facility_name), pg_temp.norm(f.name))::numeric, 2)
        FROM facilities f
        ORDER BY similarity(pg_temp.norm(t.facility_name), pg_temp.norm(f.name)) DESC LIMIT 1) AS closest_facility_anywhere
FROM tracker_raw t WHERE t.facility_id IS NULL ORDER BY t.district, t.facility_name;

\echo '== Facilities with no tracker row (stay not_started) =='
SELECT count(*) AS facilities_without_tracker_row
FROM facilities f WHERE NOT EXISTS (SELECT 1 FROM tracker_raw t WHERE t.facility_id = f.facility_code);
