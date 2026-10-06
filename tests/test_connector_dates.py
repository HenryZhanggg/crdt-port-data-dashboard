import unittest

import pandas as pd

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
