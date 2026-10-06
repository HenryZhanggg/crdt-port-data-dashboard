import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from api_connectors import empty_bundle, status_row
from data_quality import quality_table


def observation_fixture():
    bundle = empty_bundle()
    times = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("15min"), periods=12, freq="15min")
    bundle["water_levels"] = pd.DataFrame([
        {"station_reference": station, "station_label": "Liverpool", "date_time": time, "value": i / 10 + offset,
         "unit": unit, "datum": datum, "datum_uri": uri, "lat": 53.448, "lon": -3.015, "site_key": "53.448,-3.015",
         "parameter": "level", "qualifier": "Tidal Level", "api_endpoint": "https://environment.data.gov.uk/flood-monitoring/data/readings"}
        for station, unit, datum, uri, offset in [
            ("E70139", "mAOD", "Ordnance Datum Newlyn", "http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD", 0),
            ("E70124", "m", "Local tide gauge datum", "https://example.org/test/local-datum", 4.93)]
        for i, time in enumerate(times)
    ])
    bundle["webtris_sites"] = pd.DataFrame([{"site_id": "6806", "lat": 53.459, "lon": -2.999, "description": "A5036 reference counter"}])
    bundle["webtris_daily"] = pd.DataFrame({"site_id": ["6806"] * 12, "timestamp": times.tz_localize(None), "Total Volume": list(range(20, 32)), "Avg mph": [35] * 12})
    bundle["status"] = pd.DataFrame([status_row("ea_liverpool_tide_water_level_api", "EA water levels", "Water Level", "api_connected", 24, "https://environment.data.gov.uk/flood-monitoring", "Test fixture")])
    return bundle


class DashboardViewTests(unittest.TestCase):
    def test_unverified_traffic_timezone_is_not_current(self):
        table = quality_table(observation_fixture(), pd.DataFrame(), pd.DataFrame())
        self.assertEqual(table[table["Source"].eq("Traffic 6806")].iloc[0]["State"], "Timezone unverified")

    def check_views(self, bundle):
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=bundle):
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            for page in ["GIS", "Weather", "Transport", "Data Quality", "Dataset Catalogue", "Data Status", "Raw Data"]:
                next(widget for widget in app.radio if widget.label == "View").set_value(page).run()
                self.assertEqual(len(app.exception), 0, f"{page}: {app.exception}")
            next(widget for widget in app.radio if widget.label == "Time mode").set_value("Historical browsing").run()
            self.assertEqual(len(app.exception), 0, str(app.exception))

    def test_pages_with_observations(self):
        self.check_views(observation_fixture())

    def test_pages_when_apis_return_no_observations(self):
        bundle = empty_bundle()
        bundle["status"] = pd.DataFrame(columns=["connector_id", "title", "domain", "status", "records", "last_call_utc", "url", "access_note"])
        self.check_views(bundle)


if __name__ == "__main__":
    unittest.main()
