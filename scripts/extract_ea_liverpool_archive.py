"""Extract exact Liverpool tide measures from local EA daily readings CSVs.

Run with `python scripts/extract_ea_liverpool_archive.py --output-dir data
<September archive folder> <November archive folder>`.
The original nationwide files are read locally, never copied or fetched.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


MEASURE_PREFIX = "http://environment.data.gov.uk/flood-monitoring/id/measures/"
# Exact provider identities in the project water-level observation snapshot of 17 November 2026.
LIVERPOOL_MEASURES = {
    MEASURE_PREFIX + "E70124-level-tidal_level-Mean-15_min-m": "E70124",
    MEASURE_PREFIX + "E70139-anglian-level-tidal_level-Mean-15_min-mAOD": "E70139",
    MEASURE_PREFIX + "E70139-north_west-level-tidal_level-Mean-15_min-mAOD": "E70139",
}
ARCHIVE_ROOT = "https://environment.data.gov.uk/flood-monitoring/archive"
FIELDS = ("dateTime", "measure", "value")


def _archive_lines(stream, digest):
    for line in stream:
        digest.update(line)
        yield line.decode("utf-8")


def _windows(rows):
    periods = []
    for day in sorted({date.fromisoformat(row[0][:10]) for row in rows}):
        if not periods or day > periods[-1][1] + timedelta(days=1):
            periods.append([day, day])
        else:
            periods[-1][1] = day
    return [{"start_date": start.isoformat(), "end_date": end.isoformat()} for start, end in periods]


def extract_archive(inputs, output_csv, output_manifest):
    """Preserve each matching source record, including exact identifiers and original text."""
    rows = []
    files = []
    for source in sorted(inputs, key=lambda path: path.name):
        digest = hashlib.sha256()
        first_index = len(rows)
        with source.open("rb") as stream:
            reader = csv.DictReader(_archive_lines(stream, digest))
            if not set(FIELDS).issubset(reader.fieldnames or []):
                raise ValueError(f"{source.name} does not have the EA short archive columns")
            for row in reader:
                if row["measure"] in LIVERPOOL_MEASURES:
                    rows.append((row["dateTime"], row["measure"], row["value"], source.name))
        files.append({
            "filename": source.name,
            "source_url": f"{ARCHIVE_ROOT}/{source.name}",
            "sha256": digest.hexdigest(),
            "record_count": len(rows) - first_index,
        })
    if not rows:
        raise ValueError("No records matched the verified Liverpool tide measures")
    rows.sort()
    coverage = _windows(rows)
    measure_counts = Counter(row[1] for row in rows)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow((*FIELDS, "source_file"))
        writer.writerows(rows)
    manifest = {
        "dataset_id": "ea_liverpool_archive",
        "catalogue_source_id": "HS004",
        "title": "Liverpool tide gauge archive",
        "provider": "Environment Agency",
        "source_url": ARCHIVE_ROOT,
        "api_reference": "https://environment.data.gov.uk/flood-monitoring/doc/reference",
        "licence": "Open Government Licence v3.0",
        "licence_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "attribution": "this uses Environment Agency flood and river level data from the real-time data API (Beta)",
        "measure_identity_evidence": "Provider observation sample captured by CRDT on 17 November 2026.",
        "notes": [
            "Historical subset of project-held daily Environment Agency CSVs for exact Liverpool tide measures.",
            "Original dateTime, measure URI and value are preserved and the archive filename is appended.",
            "Series remain separate. No unit or datum conversion, metadata inference, deduplication or interpolation was applied.",
            "Archive dates describe observation coverage. Original publication and receipt times are unavailable.",
        ],
        "csv_sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest(),
        "record_count": len(rows),
        "first_observed_at": rows[0][0],
        "last_observed_at": rows[-1][0],
        "coverage": coverage,
        "measures": [
            {"measure": measure, "station_reference": station, "record_count": measure_counts[measure]}
            for measure, station in LIVERPOOL_MEASURES.items()
        ],
        "files": files,
    }
    output_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive_folders", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    sources = [path for folder in args.archive_folders for path in folder.glob("readings-????-??-??.csv")]
    if not all(folder.is_dir() for folder in args.archive_folders) or len(sources) != len({p.name for p in sources}):
        parser.error("Use existing archive folders containing unique daily input filenames.")
    extract_archive(sources, args.output_dir / "ea_liverpool_archive.csv",
                    args.output_dir / "ea_liverpool_archive_manifest.json")


if __name__ == "__main__":
    main()
