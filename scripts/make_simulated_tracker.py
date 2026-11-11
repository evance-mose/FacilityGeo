"""Generate a SIMULATED rollout tracker CSV from the facilities table.

The real tracker is a Ministry file and stays out of Git. This script makes a
stand-in with the same kind of mess a real tracker has, so the load / match /
update pipeline can be developed and demonstrated:

  * ~12% of facilities have no row at all (stay 'not_started')
  * some rows carry the DHIS2 code, most only a name and a district
  * names with case/spacing changes, abbreviations and typos
  * 'Mzimba' instead of 'Mzimba North' / 'Mzimba South'
  * a few invented facilities that match nothing (manual review)
  * mixed status labels and two date formats

Nothing here is real: statuses, dates, devices, staff, internet and power are
random (fixed seed), with remote districts made less likely to be live.

Usage (from the FacilityGeo folder):
    .venv/bin/python scripts/make_simulated_tracker.py
Writes data/tracker_simulated.csv (gitignored, full) and
sample_data/tracker_sample.csv (first 20 rows, committed).
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from load_orgunits import connect

ROOT = Path(__file__).resolve().parent.parent
random.seed(2026)

# Probability that a facility in the district is already live (simulated).
LIVE_RATE = {
    "Lilongwe": 0.80, "Blantyre": 0.75, "Zomba": 0.60, "Mangochi": 0.50,
    "Salima": 0.55, "Dedza": 0.45, "Ntcheu": 0.45, "Thyolo": 0.50, "Machinga": 0.40,
    "Dowa": 0.45, "Balaka": 0.45, "Mulanje": 0.35, "Phalombe": 0.30,
    "Chiradzulu": 0.55, "Mwanza": 0.35, "Mchinji": 0.35, "Ntchisi": 0.30,
    "Kasungu": 0.30, "Nkhotakota": 0.25, "Chikwawa": 0.20, "Nsanje": 0.15,
    "Neno": 0.20, "Karonga": 0.30, "Rumphi": 0.20, "Mzimba South": 0.25,
    "Mzimba North": 0.10, "Nkhata Bay": 0.12, "Chitipa": 0.08, "Likoma": 0.0,
}
STATUS_LABELS = {
    "live": ["Live", "Live", "Live", "Go-live", "Completed"],
    "in_progress": ["In progress", "In progress", "Ongoing", "Installation"],
    "not_started": ["Not started", "Not started", "Pending", "Planned"],
}
INVENTED = [
    ("Mapale Community Clinic", "Lilongwe"), ("Chimwemwe Private Clinic", "Blantyre"),
    ("Kalimbuka Health Post", "Mzimba"), ("Upper Shire Outreach", "Machinga"),
    ("Njewa Mobile Unit", "Lilongwe"), ("Chintheche Mission Clinic", "Nkhata Bay"),
    ("Lake View Dispensary", "Salima"), ("Songani Estate Clinic", "Zomba"),
]


def noisy_name(name: str) -> str:
    r = random.random()
    if r < 0.65:
        return name
    if r < 0.75:
        return random.choice([name.lower(), name.upper(), f"  {name} ", name.replace(" ", "  ")])
    if r < 0.85:
        return (name.replace("Health Centre", "HC").replace("Health Center", "HC")
                    .replace("Dispensary", "Disp.").replace("Hospital", "Hosp."))
    if len(name) > 5:  # typo: drop or swap a letter
        i = random.randrange(1, len(name) - 2)
        return name[:i] + name[i + 1:] if random.random() < 0.5 else name[:i] + name[i + 1] + name[i] + name[i + 2:]
    return name


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y") if random.random() < 0.5 else d.isoformat()


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT facility_code, name, district FROM facilities ORDER BY facility_code")
        facilities = cur.fetchall()

    rows = []
    for code, name, district in facilities:
        if random.random() < 0.12:
            continue  # not in the tracker at all
        live_p = LIVE_RATE.get(district, 0.35)
        r = random.random()
        if r < live_p:
            status = "live"
        elif r < live_p + (1 - live_p) * 0.30:
            status = "in_progress"
        else:
            status = "not_started"
        remote = live_p < 0.3
        if status == "live":
            devices, staff = random.randint(2, 6), random.randint(4, 15)
            internet, power = random.random() < 0.92, random.random() < 0.95
            go_live = fmt_date(date(2024, 1, 15) + timedelta(days=random.randint(0, 1000)))
        elif status == "in_progress":
            devices, staff = random.randint(1, 3), random.randint(0, 8)
            internet, power = random.random() < 0.6, random.random() < 0.8
            go_live = ""
        else:
            devices, staff = 0, random.randint(0, 2)
            internet, power = random.random() < (0.25 if remote else 0.5), random.random() < (0.45 if remote else 0.7)
            go_live = ""
        tracker_district = "Mzimba" if district.startswith("Mzimba ") else district
        rows.append({
            "Facility Name": noisy_name(name),
            "District": tracker_district,
            "DHIS2 Code": code if random.random() < 0.25 else "",
            "Status": random.choice(STATUS_LABELS[status]),
            "Go-Live Date": go_live,
            "Devices Installed": devices,
            "Staff Trained": staff,
            "Internet": "Yes" if internet else "No",
            "Power": "Yes" if power else "No",
        })
    for name, district in INVENTED:
        rows.append({"Facility Name": name, "District": district, "DHIS2 Code": "", "Status": "Not started",
                     "Go-Live Date": "", "Devices Installed": 0, "Staff Trained": 0,
                     "Internet": "No", "Power": "No"})
    random.shuffle(rows)

    fields = list(rows[0])
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "sample_data").mkdir(exist_ok=True)
    for path, subset in ((ROOT / "data" / "tracker_simulated.csv", rows),
                         (ROOT / "sample_data" / "tracker_sample.csv", rows[:20])):
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(subset)
        print(f"wrote {len(subset)} rows to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
