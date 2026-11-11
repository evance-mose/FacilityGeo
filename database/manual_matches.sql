-- Manual tracker matches, applied at the end of database/match_tracker.sql.
-- Add one line per decision made by hand after reviewing the UNMATCHED report.
-- Keyed by tracker name + district (not row_id), so it survives a CSV reload.
--
-- Example (replace with real decisions):
--   ('Chimwemwe Private Clinic', 'Blantyre', 'abc123UID45'),
--
-- facility_code is the DHIS2 UID from facilities.facility_code.
-- When two facilities are true duplicates in DHIS2 (e.g. Ulumba Namatope-(WS)
-- in Zomba), pick one UID here; the other keeps the default not_started.

CREATE TEMP TABLE IF NOT EXISTS manual_matches (
    tracker_name     TEXT,
    tracker_district TEXT,
    facility_code    TEXT
);
TRUNCATE manual_matches;

-- Decisions below were made for data/tracker_simulated.csv. A different
-- tracker simply will not match these names and they do nothing.
INSERT INTO manual_matches (tracker_name, tracker_district, facility_code) VALUES
    -- DHIS2 has two near-identical records at one point (differ only by brackets):
    ('Chizumulo (St Marys) Health Centre', 'Likoma', 'Kzo3T3VQUwH'),
    ('Chizumulo St Marys Heatlh Centre',   'Likoma', 'XXjX57Xslam'),
    -- Typo with a clear single candidate just below the fuzzy threshold:
    ('Chagnda', 'Salima', 'fe9EboFXU0V'),
    -- True DHIS2 duplicate (same name, same coordinates, two UIDs): one row each.
    ('Ulumba Namatope-(WS)',  'Zomba', 'rP44Po0Le85'),
    ('UlumbaN amatope-(WS)',  'Zomba', 'u7i5Cr1ayFu');
-- Left unmatched on purpose: 8 tracker rows for facilities that are not in
-- DHIS2 (Chimwemwe Private Clinic, Mapale Community Clinic, ...).

UPDATE tracker_raw t
SET facility_id = m.facility_code, match_method = 'manual'
FROM manual_matches m
JOIN facilities f ON f.facility_code = m.facility_code
WHERE t.facility_name = m.tracker_name
  AND t.district = m.tracker_district
  AND t.facility_id IS NULL;
