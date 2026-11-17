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

    def test_water_preserves_source_identifiers(self):
        station_uri = "http://environment.data.gov.uk/flood-monitoring/id/stations/E70139"
        measure_uri = "http://environment.data.gov.uk/flood-monitoring/id/measures/E70139-level"
        reading_uri = "http://environment.data.gov.uk/flood-monitoring/data/readings/E70139-20261005"
        session = Session(water=True)
        with patch.object(session, "get", side_effect=[
            Response({"items": [{"@id": station_uri, "stationReference": "E70139", "measures": []}]}),
            Response({"items": [{"@id": reading_uri, "measure": {"@id": measure_uri},
                "dateTime": "2026-10-05T12:00:00Z", "value": 1.2}]}),
        ]):
            frame, _ = fetch_liverpool_tide_water_levels(session)
        self.assertTrue({"station_uri", "measure_uri", "reading_uri"}.issubset(frame.columns))
        row = frame.iloc[0]
        self.assertEqual(row["station_uri"], station_uri)
        self.assertEqual(row["measure_uri"], measure_uri)
        self.assertEqual(row["reading_uri"], reading_uri)

    def test_water_keeps_string_measure_reference_without_metadata(self):
        measure_uri = "http://environment.data.gov.uk/flood-monitoring/id/measures/unlisted"
        session = Session(water=True)
        with patch.object(session, "get", side_effect=[
            Response({"items": [{"stationReference": "E70139", "measures": []}]}),
            Response({"items": [{"measure": measure_uri,
                "dateTime": "2026-10-05T12:00:00Z", "value": 1.2}]}),
        ]) as get:
            frame, _ = fetch_liverpool_tide_water_levels(session)
        row = frame.iloc[0]
        self.assertEqual(row.get("measure_uri", ""), measure_uri)
        self.assertEqual(row["station_uri"], "")
        self.assertEqual(row["reading_uri"], "")
        self.assertEqual(get.call_count, 2)

    def test_water_dedup_preserves_distinct_measurements_and_values(self):
        measure = {"@id": "https://example.org/measure/a", "parameter": "level",
            "qualifier": "tidal_level", "unitName": "m",
            "datumType": "http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD"}
        variants = [
            {"datumType": "http://environment.data.gov.uk/flood-monitoring/def/core/datumLocal"},
            {"@id": "https://example.org/measure/b"},
            {"parameter": "flow"},
            {"qualifier": "river_level"},
        ]
        reading = {"measure": measure, "dateTime": "2026-10-05T12:00:00Z", "value": 1.2}
        readings = [reading, reading.copy(), dict(reading, value=1.3)]
        readings.extend(dict(reading, measure={**measure, **variant}) for variant in variants)
        session = Session(water=True)
        with patch.object(session, "get", side_effect=[
            Response({"items": [{"stationReference": "E70139", "measures": []}]}),
            Response({"items": readings}),
        ]):
            frame, _ = fetch_liverpool_tide_water_levels(session)
        self.assertEqual(len(frame), 6)
        self.assertEqual(set(frame["value"]), {1.2, 1.3})
        self.assertEqual(frame["datum_uri"].nunique(), 2)
        self.assertEqual(frame["measure_uri"].nunique(), 2)

    def test_water_dedup_preserves_distinct_source_reading_ids(self):
        reading = {"@id": "https://example.org/readings/a", "measure": "https://example.org/measure",
            "dateTime": "2026-10-05T12:00:00Z", "value": 1.2}
        session = Session(water=True)
        with patch.object(session, "get", side_effect=[
            Response({"items": [{"stationReference": "E70139", "measures": []}]}),
            Response({"items": [reading, reading.copy(), {**reading, "@id": "https://example.org/readings/b"}]}),
        ]):
            frame, _ = fetch_liverpool_tide_water_levels(session)
        self.assertEqual(len(frame), 2)
        self.assertEqual(set(frame["reading_uri"]),
            {"https://example.org/readings/a", "https://example.org/readings/b"})

    def test_traffic_query_is_not_fixed_to_2024(self):
        session = Session()
        fetch_webtris(session, "2026-10-05", "2026-10-06")
        params = session.calls[-1][1]["params"]
        self.assertEqual(params["start_date"], "05102026")
        self.assertEqual(params["end_date"], "06102026")

    def test_traffic_no_content_preserves_sites_and_explicit_empty_status(self):
        session=Session()
        original_get=session.get
        class NoContent(Response):
            status_code=204
            def json(self):
                raise ValueError('No response body')
        def get(url,**kwargs):
            return original_get(url,**kwargs) if url.endswith('/sites') else NoContent(None)
        with patch.object(session,'get',side_effect=get):
            frames,statuses=fetch_webtris(session,'2026-10-05','2026-10-06')
        self.assertFalse(frames['webtris_sites'].empty)
        self.assertTrue(frames['webtris_daily'].empty)
        report=next(row for row in statuses if row['connector_id']=='webtris_daily_a5036_api')
        self.assertEqual(report['status'],'api_no_data')
        self.assertIn('204',report['access_note'])


if __name__ == "__main__":
    unittest.main()
