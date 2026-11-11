-- Manual tracker matches, applied at the end of database/match_tracker.sql.
-- Add one line per decision made by hand after reviewing the UNMATCHED report.
-- Keyed by tracker name + district (not row_id), so it survives a CSV reload.
--
-- facility_code is the DHIS2 UID from facilities.facility_code (find it with
--   SELECT facility_code, name, district FROM facilities WHERE name ILIKE '%word%';).
-- When two DHIS2 records are true duplicates, pick one UID here; the other
-- stays 'not_in_tracker'.

CREATE TEMP TABLE IF NOT EXISTS manual_matches (
    tracker_name     TEXT,
    tracker_district TEXT,
    facility_code    TEXT
);
TRUNCATE manual_matches;

INSERT INTO manual_matches (tracker_name, tracker_district, facility_code) VALUES
    -- Kamuzu Central Hospital is listed in DHIS2 under its old name, Lilongwe Central Hospital.
    ('Kamuzu Central Hospital', 'Lilongwe', 'cFiiWO0mSVO');
-- Still unmatched (no safe candidate, or two equally likely DHIS2 records) and
-- waiting for a decision: Amecca, Chipande, Kachere, Khungulu, Nancholi, Ntonda,
-- Soche Health Centre, Chilomoni, Zingwangwa (Blantyre); Biwi Health Centre
-- (Lilongwe); Kaluluma HC (Kasungu); Mzuzu Central Hospital (Mzimba North).

UPDATE tracker_raw t
SET facility_id = m.facility_code, match_method = 'manual'
FROM manual_matches m
JOIN facilities f ON f.facility_code = m.facility_code
WHERE t.facility_name = m.tracker_name
  AND t.district = m.tracker_district
  AND t.facility_id IS NULL;
