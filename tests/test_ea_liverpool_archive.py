import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.extract_ea_liverpool_archive import extract_archive


class LiverpoolArchiveTests(unittest.TestCase):
    def test_extraction_preserves_exact_measure_and_original_values(self):
        prefix = "http://environment.data.gov.uk/flood-monitoring/id/measures/"
        first_measure = prefix + "E70139-anglian-level-tidal_level-Mean-15_min-mAOD"
        second_measure = prefix + "E70139-north_west-level-tidal_level-Mean-15_min-mAOD"
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "readings-2025-09-05.csv"
            source.write_text(
                "dateTime,measure,value\n"
                f"2025-09-05T00:15:00Z,{first_measure},1.300\n"
                f"2025-09-05T00:00:00Z,{second_measure},1.400\n"
                f"2025-09-05T00:00:00Z,{prefix}E70139-other,6.000\n",
                encoding="utf-8",
            )
            out_csv = folder / "subset.csv"
            out_manifest = folder / "manifest.json"
            extract_archive([source], out_csv, out_manifest)
            with out_csv.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            manifest = json.loads(out_manifest.read_text(encoding="utf-8"))

            self.assertEqual([row["measure"] for row in rows], [second_measure, first_measure])
            self.assertEqual([row["value"] for row in rows], ["1.400", "1.300"])
            self.assertEqual([row["source_file"] for row in rows], [source.name] * 2)
            self.assertEqual(manifest["record_count"], 2)
            self.assertEqual(manifest["first_observed_at"], "2025-09-05T00:00:00Z")
            self.assertEqual(manifest["last_observed_at"], "2025-09-05T00:15:00Z")
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(manifest["csv_sha256"], hashlib.sha256(out_csv.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
