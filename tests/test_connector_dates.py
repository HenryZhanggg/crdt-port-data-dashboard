import unittest
from unittest.mock import patch

import pandas as pd

import api_connectors
from api_connectors import fetch_liverpool_tide_water_levels, fetch_webtris


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Session:
    def __init__(self, water=False):
        self.calls = []
        self.water = water

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "TideGauge" in url:
            return Response({"items": [{"stationReference": "E70139", "lat": 53.448, "long": -3.015,
                "measures": [{"@id": "https://example.org/measure", "unitName": "mAOD", "datumType": "http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD"}]}]})
        if "data/readings" in url:
            return Response({"items": [{"measure": "https://example.org/measure", "dateTime": "2026-10-05T12:00:00Z", "value": 1.2}]})
        if url.endswith("/sites"):
            return Response({"sites": [{"Id": "6806", "Name": "A5036", "Description": "A5036", "Longitude": -3.0, "Latitude": 53.45, "Status": "Active"}]})
        return Response({"Rows": []})


class ConnectorDateTests(unittest.TestCase):
    def test_water_only_loading_does_not_fetch_other_feeds(self):
        with patch.object(api_connectors, "request_session", return_value=Session(water=True)), \
             patch.object(api_connectors, "fetch_webtris") as traffic, \
             patch.object(api_connectors, "fetch_dft_port_statistics") as shipping:
            result = api_connectors.fetch_raw_data_bundle("2026-10-05", "2026-10-06", sources=("water_level",))
            self.assertEqual(len(result["water_levels"]), 1)
            traffic.assert_not_called()
            shipping.assert_not_called()

    def test_failed_selected_source_is_reported(self):
        with patch.object(api_connectors, "fetch_liverpool_tide_water_levels", side_effect=RuntimeError("Upstream unavailable")):
            result = api_connectors.fetch_raw_data_bundle(sources=("water_level",))
            row = result["status"][result["status"]["connector_id"].eq("water_level_api")].iloc[0]
            self.assertEqual(row["status"], "api_error")
            self.assertIn("Upstream unavailable", row["access_note"])

    def test_water_query_uses_selected_dates_and_measure_datum(self):
        session = Session(water=True)
        frame, _ = fetch_liverpool_tide_water_levels(session, "2026-10-05", "2026-10-06")
        params = session.calls[-1][1]["params"]
        self.assertEqual(params["startdate"], "2026-10-05")
        self.assertEqual(params["enddate"], "2026-10-06")
        self.assertIn("Ordnance", frame.iloc[0]["datum"])
        self.assertEqual(frame.iloc[0]["unit"], "mAOD")

    def test_traffic_query_is_not_fixed_to_2024(self):
        session = Session()
        fetch_webtris(session, "2026-10-05", "2026-10-06")
        params = session.calls[-1][1]["params"]
        self.assertEqual(params["start_date"], "05102026")
        self.assertEqual(params["end_date"], "06102026")


if __name__ == "__main__":
    unittest.main()
