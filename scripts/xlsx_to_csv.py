"""Convert the first sheet of an .xlsx file to CSV (standard library only).

Usage (from the FacilityGeo folder):
    python scripts/xlsx_to_csv.py "/path/to/tracker.xlsx" data/tracker_real.csv

Spreadsheets often have blank rows above the table and thousands of empty
formatted rows below it. This script treats the first row with at least two
filled cells as the header, drops rows that are completely empty, and strips
spaces. Column names are kept as they are: scripts/load_tracker.py maps them.
Nothing is sent anywhere; the output stays on disk (data/ is ignored by Git).
"""
import csv
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_rows(path: str):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{{{NS}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS}}}t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    for row in sheet.iter(f"{{{NS}}}row"):
        cells = {}
        for c in row.findall(f"{{{NS}}}c"):
            v = c.find(f"{{{NS}}}v")
            if v is not None:
                cells[column_index(c.get("r"))] = shared[int(v.text)] if c.get("t") == "s" else v.text
            else:
                inline = c.find(f"{{{NS}}}is")
                if inline is not None:
                    cells[column_index(c.get("r"))] = "".join(t.text or "" for t in inline.iter(f"{{{NS}}}t"))
        if cells:
            width = max(cells) + 1
            yield [(cells.get(i) or "").strip() for i in range(width)]


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    rows = list(read_rows(src))
    header_at = next((i for i, r in enumerate(rows) if sum(1 for x in r if x) >= 2), None)
    if header_at is None:
        sys.exit("no header row found (need a row with at least two filled cells)")
    header = rows[header_at]
    body = [r + [""] * (len(header) - len(r)) for r in rows[header_at + 1:] if any(r)]
    body = [r[: len(header)] for r in body]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(body)
    print(f"{src}: header {header!r}; wrote {len(body)} rows to {dst}")


if __name__ == "__main__":
    main()
