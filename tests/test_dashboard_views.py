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
            for section, pages in [
                ("Monitoring", ["GIS", "Observation Explorer", "Transport", "Data Quality"]),
                ("Data & Research", ["Research & Replay", "Report Centre", "Dataset Catalogue", "Data Status", "Raw Data"]),
            ]:
                next(widget for widget in app.radio if widget.label == "Workspace").set_value(section).run()
                for page in pages:
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

    def test_stale_water_is_not_labelled_unavailable_on_home(self):
        bundle = observation_fixture()
        bundle["water_levels"]["date_time"] -= pd.Timedelta(days=1)
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=bundle):
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
            self.assertTrue(any("<strong>Stale</strong>" in item.value for item in app.markdown))

    def test_explorer_loads_only_water_source(self):
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=observation_fixture()) as fetch:
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
            fetch.reset_mock()
            st.cache_data.clear()
            next(widget for widget in app.radio if widget.label == "View").set_value("Observation Explorer").run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            self.assertEqual([call.kwargs["sources"] for call in fetch.call_args_list], [("water_level",)])

    def test_replay_cursor_changes_the_eight_point_window(self):
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=observation_fixture()):
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
            next(widget for widget in app.radio if widget.label == "Workspace").set_value("Data & Research").run()
            next(widget for widget in app.radio if widget.label == "View").set_value("Research & Replay").run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            cursor = next(widget for widget in app.slider if widget.label == "Replay checkpoint")
            cursor.set_value(7).run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            self.assertTrue(any("105" in item.value for item in app.caption))

    def test_partner_without_weather_access_cannot_open_explorer(self):
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=observation_fixture()):
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
            next(widget for widget in app.radio if widget.label == "View").set_value("Observation Explorer").run()
            next(widget for widget in app.selectbox if widget.label == "Partner").set_value("Terminal operator").run()
            self.assertEqual(len(app.exception), 0, str(app.exception))
            pages = next(widget for widget in app.radio if widget.label == "View").options
            self.assertNotIn("Observation Explorer", pages)
            next(widget for widget in app.radio if widget.label == "Workspace").set_value("Data & Research").run()
            pages = next(widget for widget in app.radio if widget.label == "View").options
            self.assertNotIn("Research & Replay", pages)

    def test_map_freshness_matches_displayed_measurement_reference(self):
        bundle = observation_fixture()
        water = bundle["water_levels"]
        fresh = water[water["station_reference"].eq("E70139")].copy()
        stale = fresh.assign(unit="m", datum_uri="datum:local", datum="Local datum",
            date_time=fresh["date_time"] - pd.Timedelta(days=1))
        bundle["water_levels"] = pd.concat([stale, fresh])
        decks = []
        def capture(deck, **kwargs):
            decks.append(deck)
            return {"selection": {"objects": {}}}
        st.cache_data.clear()
        with patch("api_connectors.fetch_raw_data_bundle", return_value=bundle), patch("monitoring_views.st.pydeck_chart", side_effect=capture):
            app = AppTest.from_file("app.py", default_timeout=30)
            app.session_state["dashboard_authorised"] = True
            app.run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        points = next(layer.data for layer in decks[-1].layers if layer.id == "monitoring-points")
        self.assertEqual(points[0]["unit"], "mAOD")
        self.assertEqual(points[0]["state"], "Current")



if __name__ == "__main__":
    unittest.main()
