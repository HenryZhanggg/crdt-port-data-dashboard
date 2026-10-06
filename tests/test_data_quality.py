import unittest

import pandas as pd

from data_quality import (
    assess_series,
    compatibility,
    filter_dates,
    measure_datum,
    observation_graph,
    validate_observations,
)


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp("2026-10-06T12:00:00Z")

    def test_connected_old_observations_are_stale(self):
        frame = pd.DataFrame({"time": ["2024-05-01T12:00:00Z"]})
        result = assess_series("Traffic", frame, "time", "Observation", self.now, 180)
        self.assertEqual(result["State"], "Stale")

    def test_sample_is_never_current(self):
        frame = pd.DataFrame({"time": [self.now]})
        self.assertEqual(assess_series("Weather", frame, "time", "Sample", self.now)["State"], "Sample")

    def test_missing_and_future_times_are_distinguished(self):
        invalid = pd.DataFrame({"time": ["invalid"]})
        future = pd.DataFrame({"time": ["2026-10-06T13:00:00Z"]})
        self.assertEqual(assess_series("Water", invalid, "time", "Observation", self.now)["State"], "Unknown time")
        self.assertEqual(assess_series("Water", future, "time", "Observation", self.now)["State"], "Future timestamp")

    def test_date_filter_includes_whole_end_date(self):
        frame = pd.DataFrame({"time": ["2026-10-05T23:59:00Z", "2026-10-06T23:59:59Z", "2026-10-07T00:00:00Z"]})
        result = filter_dates(frame, "time", "2026-10-06", "2026-10-06")
        self.assertEqual(len(result), 1)

    def test_gap_count_and_invalid_values(self):
        frame = pd.DataFrame({"time": ["2026-10-06T11:00Z", "2026-10-06T11:15Z", "2026-10-06T11:45Z"], "value": [1, "invalid", 2]})
        result = assess_series("Water", frame, "time", "Observation", self.now, 60, "value", 15)
        self.assertEqual(result["Missing intervals"], 1)
        self.assertEqual(result["Invalid values"], 1)

    def test_infinite_values_are_not_valid_observations(self):
        frame = pd.DataFrame({"time": [self.now] * 3, "value": [float("inf"), float("-inf"), "invalid"]})
        result = assess_series("Water", frame, "time", "Observation", self.now, value_column="value")
        self.assertEqual(result["Invalid values"], 3)

    def test_datum_requires_source_metadata(self):
        label, uri = measure_datum({"unitName": "m"})
        self.assertEqual(label, "Unknown datum")
        self.assertEqual(uri, "")
        label, uri = measure_datum({"datumType": "http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD"})
        self.assertIn("Ordnance", label)

    def test_unit_match_does_not_override_datum_mismatch(self):
        left = {"unit": "m", "datum_uri": "datum:a", "site_key": "Liverpool", "parameter": "level", "qualifier": "tidal_level"}
        right = dict(left, datum_uri="datum:b")
        self.assertFalse(compatibility(left, right)[0])
        self.assertIn("datum", compatibility(left, right)[1].lower())
        self.assertFalse(compatibility(left, dict(left, datum_uri=""))[0])
        self.assertFalse(compatibility(left, dict(left, site_key="Hull"))[0])
        self.assertTrue(compatibility(left, left)[0])

    def test_real_graph_validation_detects_missing_datum(self):
        frame = pd.DataFrame([{"station_reference": "E70139", "station_label": "Liverpool", "date_time": "2026-10-06T11:45:00Z", "value": 1.2, "unit": "mAOD", "datum_uri": "http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD", "parameter": "level", "qualifier": "tidal_level", "lat": 53.4, "lon": -3.0}])
        graph = observation_graph(frame)
        conforms, issues = validate_observations(graph)
        self.assertTrue(conforms)
        self.assertTrue(issues.empty)
        conforms, issues = validate_observations(observation_graph(frame.drop(columns="datum_uri")))
        self.assertFalse(conforms)
        self.assertTrue(issues["Message"].str.contains("datum", case=False).any())
        conflicting = frame.copy()
        conflicting["datum_uri"] = "https://example.org/test/local-datum"
        conforms, issues = validate_observations(observation_graph(conflicting))
        self.assertFalse(conforms)
        self.assertTrue(issues["Message"].str.contains("Ordnance", case=False).any())
        conforms, issues = validate_observations(observation_graph(frame.drop(columns="lat")))
        self.assertFalse(conforms)
        self.assertTrue(issues["Message"].str.contains("latitude", case=False).any())


if __name__ == "__main__":
    unittest.main()
