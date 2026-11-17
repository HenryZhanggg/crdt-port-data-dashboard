import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ValidationReportEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads((ROOT / "data" / "validation_report.json").read_text(encoding="utf-8"))

    def test_report_revision_and_date_are_traceable(self):
        report = self.evidence["report"]
        self.assertEqual(report["reference"], "P0940-REP-103")
        self.assertEqual(report["revision"], "C1")
        self.assertEqual(report["date"], "2026-11-04")
        self.assertEqual(report["page_count"], 182)
        self.assertEqual(report["evidence_status"], "report_assessment")

    def test_existing_catalogue_ids_are_covered_once(self):
        catalogue = json.loads((ROOT / "data" / "high_score_dataset_catalog.json").read_text(encoding="utf-8"))
        source_ids = [source["source_id"] for source in self.evidence["sources"]]
        self.assertEqual(set(source_ids), {source["source_id"] for source in catalogue})
        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_source_findings_have_valid_page_evidence_or_explicit_unmapped_status(self):
        for source in self.evidence["sources"]:
            with self.subTest(source=source["source_id"]):
                self.assertTrue(source["label"])
                self.assertTrue(source["temporal_role"])
                self.assertTrue(source["access_assessment"])
                self.assertTrue(source["required_checks"])
                if source["evidence_status"] == "report_assessment":
                    self.assertTrue(source["report_pages"])
                    self.assertTrue(source["report_section"])
                    self.assertTrue(source["findings"])
                else:
                    self.assertEqual(source["evidence_status"], "not_mapped")
                    self.assertEqual(source["report_pages"], [])
                self.assertTrue(all(type(page) is int and 1 <= page <= 182 for page in source["report_pages"]))
                self.assertNotIn("runtime_checked_at", source)
                self.assertNotIn("connected", source)

    def test_delayed_and_aggregate_sources_are_not_presented_as_live(self):
        sources = {source["source_id"]: source for source in self.evidence["sources"]}
        self.assertEqual(sources["HS007"]["temporal_role"], "Historical observations")
        self.assertIn("month", " ".join(sources["HS007"]["limitations"]).lower())
        self.assertEqual(sources["HS014"]["temporal_role"], "Weekly aggregate")
        self.assertEqual(sources["HS011"]["evidence_status"], "not_mapped")
        self.assertIn("redistribution", " ".join(sources["HS012"]["limitations"]).lower())

    def test_project_recommendations_retain_report_pages(self):
        for recommendation in self.evidence["recommendations"]:
            self.assertTrue(recommendation["id"])
            self.assertTrue(recommendation["action"])
            self.assertTrue(recommendation["report_pages"])
            self.assertTrue(all(type(page) is int and 1 <= page <= 182 for page in recommendation["report_pages"]))


if __name__ == "__main__":
    unittest.main()
