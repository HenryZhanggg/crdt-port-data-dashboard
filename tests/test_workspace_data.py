import io
import json
import unittest
import zipfile

import numpy as np
import pandas as pd

from workspace_data import clean_water_series, quality_findings, report_archive, window_features


def series_fixture():
    return pd.DataFrame({
        "date_time": pd.date_range("2026-10-06T08:00Z", periods=10, freq="15min"),
        "value": np.arange(10, dtype=float), "station_reference": "E70139", "unit": "mAOD",
        "datum": "Ordnance Datum Newlyn", "datum_uri": "datum:a", "station_label": "Liverpool",
        "api_endpoint": "https://environment.data.gov.uk/flood-monitoring/data/readings",
        "retrieved_at_utc": "2026-10-06T11:00:00Z",
    })


class WorkspaceDataTests(unittest.TestCase):
    def test_rate_uses_elapsed_time_and_does_not_bridge_gap(self):
        data = series_fixture().drop(index=2)
        result = clean_water_series(data)
        self.assertEqual(result.iloc[1]["rate_per_hour"], 4)
        self.assertTrue(pd.isna(result.iloc[2]["rate_per_hour"]))

    def test_multiple_references_are_rejected(self):
        other = series_fixture().assign(datum_uri="datum:b")
        with self.assertRaisesRegex(ValueError, "reference"):
            clean_water_series(pd.concat([series_fixture(), other]))

    def test_numeric_errors_and_duplicates_remain_visible(self):
        data = series_fixture().astype({"value": object})
        data.loc[2, "value"] = "invalid"
        result = clean_water_series(pd.concat([data, data.iloc[[0]]]))
        self.assertEqual(len(result), 10)
        self.assertTrue(pd.isna(result.iloc[2]["value"]))
        self.assertTrue(pd.isna(result.iloc[3]["rate_per_hour"]))

    def test_conflicting_duplicates_invalidate_the_window(self):
        data = series_fixture().iloc[:8]
        duplicate = data.iloc[[3]].assign(value=99)
        result = clean_water_series(pd.concat([data, duplicate]))
        self.assertTrue(result.iloc[3]["duplicate_conflict"])
        self.assertTrue(pd.isna(result.iloc[3]["value"]))
        self.assertFalse(window_features(result)["valid"])
        self.assertTrue(pd.isna(result.iloc[4]["rate_per_hour"]))

    def test_chart_preserves_off_cadence_observations_and_inserts_gaps(self):
        from workspace_data import water_chart_series
        data = series_fixture()
        data.loc[3, "date_time"] += pd.Timedelta(minutes=1)
        chart = water_chart_series(data)
        self.assertEqual(chart.loc[data.loc[3, "date_time"]], 3)
        self.assertTrue(pd.isna(chart.loc[pd.Timestamp("2026-10-06T08:45Z")]))

    def test_report_preserves_off_cadence_observations(self):
        data = series_fixture()
        data.loc[3, "date_time"] += pd.Timedelta(minutes=1)
        with zipfile.ZipFile(io.BytesIO(report_archive({"water_levels": data}, pd.DataFrame(), "2026-10-06", "2026-10-06"))) as archive:
            self.assertTrue("08:46" in archive.read("report.html").decode(), "Report chart dropped an off-cadence timestamp")

    def test_window_is_eight_past_samples_spanning_105_minutes(self):
        data = clean_water_series(series_fixture())
        values = window_features(data.iloc[:8])
        self.assertTrue(values["valid"])
        self.assertEqual(values["duration_minutes"], 105)
        self.assertEqual(values["net_change"], 7)
        self.assertEqual(values["range"], 7)
        self.assertEqual(values["max_step"], 1)
        self.assertAlmostEqual(values["trend_per_hour"], 4)

    def test_incomplete_gapped_or_invalid_window_is_not_model_ready(self):
        data = clean_water_series(series_fixture())
        self.assertFalse(window_features(data.iloc[:7])["valid"])
        self.assertFalse(window_features(data.drop(index=2).iloc[:8])["valid"])
        data.loc[2, "value"] = np.nan
        self.assertFalse(window_features(data.iloc[:8])["valid"])

    def test_health_findings_distinguish_stale_from_absent(self):
        table = pd.DataFrame([
            {"Source": "Water A", "Kind": "Observation", "State": "Stale", "Missing intervals": 2},
            {"Source": "Traffic A", "Kind": "Observation", "State": "Timezone unverified"},
            {"Source": "Weather example", "Kind": "Sample", "State": "Sample"},
        ])
        result = quality_findings(table)
        self.assertTrue(result["Finding"].str.contains("past the freshness budget").any())
        self.assertTrue(result["Finding"].str.contains("timezone", case=False).any())
        self.assertFalse(result["Source"].eq("Weather example").any())

    def test_export_contains_selected_data_and_reference_separated_charts(self):
        water = series_fixture()
        other = water.assign(station_reference="E70124", unit="m", datum_uri="datum:b", datum="Local datum")
        bundle = {"water_levels": pd.concat([water, other]), "status": pd.DataFrame(), "webtris_daily": pd.DataFrame()}
        quality = pd.DataFrame({"Source": ["<script>bad</script>"], "State": ["Stale"]})
        payload = report_archive(bundle, quality, "2026-10-06", "2026-10-06")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(pd.read_csv(archive.open("water_observations.csv"))), 20)
            metadata = json.loads(archive.read("metadata.json"))
            self.assertEqual(metadata["selected_start"], "2026-10-06")
            self.assertEqual(metadata["water_records"], 20)
            self.assertIn("exported_at_utc", metadata)
            html = archive.read("report.html").decode()
            self.assertIn("&lt;script&gt;bad&lt;/script&gt;", html)
            self.assertNotIn("<script>bad</script>", html)
            self.assertIn("E70139", html)
            self.assertIn("E70124", html)
            self.assertIn("No datum conversion", html)

    def test_empty_data_exports_a_valid_report(self):
        payload = report_archive({}, pd.DataFrame(), "2026-10-05", "2026-10-06")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(json.loads(archive.read("metadata.json"))["water_records"], 0)
            self.assertIn("No water observations", archive.read("report.html").decode())

    def test_export_excludes_rows_outside_the_selected_dates(self):
        data = pd.concat([series_fixture(), series_fixture().assign(date_time=lambda x: x["date_time"] - pd.Timedelta(days=1))])
        with zipfile.ZipFile(io.BytesIO(report_archive({"water_levels": data}, pd.DataFrame(), "2026-10-06", "2026-10-06"))) as archive:
            self.assertEqual(len(pd.read_csv(archive.open("water_observations.csv"))), 10)


if __name__ == "__main__":
    unittest.main()
