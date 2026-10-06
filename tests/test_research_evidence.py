import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from research_views import playback_figure
from monitoring_views import water_level_figure
from test_workspace_data import series_fixture

BASE = Path(__file__).resolve().parents[1]


class ResearchEvidenceTests(unittest.TestCase):
    def test_evidence_mean_and_sd_match_per_fold_records(self):
        summary = pd.read_csv(BASE / "data/research_signature_summary.csv")
        folds = pd.read_csv(BASE / "data/research_signature_folds.csv")
        manifest = json.loads((BASE / "data/research_provenance.json").read_text())
        self.assertEqual(manifest["independent_clusters"], 4)
        self.assertEqual(len(manifest["source_sha256"]), 64)
        for _, row in summary.iterrows():
            group = folds[folds["feature_group"].eq(row["feature_group"])]
            self.assertEqual(len(group), 4)
            self.assertAlmostEqual(group["test_ap"].mean(), row["test_ap_mean"])
            self.assertAlmostEqual(group["sparse_f2"].mean(), row["sparse_f2_mean"])
            self.assertAlmostEqual(group["test_ap"].std(), row["test_ap_std"])

    def test_playback_frames_use_no_future_observations(self):
        data = series_fixture()
        figure = playback_figure(data)
        self.assertTrue(figure.frames)
        for frame in figure.frames:
            checkpoint = int(frame.name)
            for trace in frame.data:
                times = pd.to_datetime(list(trace.x), utc=True)
                self.assertTrue((times <= data.iloc[checkpoint]["date_time"]).all())

    def test_playback_preserves_off_cadence_observations(self):
        data = series_fixture()
        data.loc[3, "date_time"] += pd.Timedelta(minutes=1)
        figure = playback_figure(data)
        self.assertIn(data.loc[3, "date_time"], list(figure.frames[-1].data[0].x))

    def test_gap_shapes_are_assigned_in_bulk(self):
        data = series_fixture().iloc[::2].reset_index(drop=True)
        with patch("plotly.graph_objects.Figure.add_vrect") as rectangle:
            figure = water_level_figure(data)
        self.assertEqual(len(figure.layout.shapes), 4)
        rectangle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
