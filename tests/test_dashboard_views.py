import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from api_connectors import empty_bundle, status_row
from data_quality import quality_table
from test_daily_views import daily_fixture


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
    def setUp(self):
        st.cache_data.clear()
        daily = patch('daily_service.load_daily_snapshot', return_value=daily_fixture())
        daily.start()
        self.addCleanup(daily.stop)

    def app(self, bundle=None, standalone=False, **state):
        fetch = patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture() if bundle is None else bundle)
        self.fetch = fetch.start()
        self.addCleanup(fetch.stop)
        if standalone:
            code = """import json
from pathlib import Path
import pandas as pd
from api_connectors import fetch_raw_data_bundle
from monitor_workspace import render_monitor_workspace

def load_bundle(start, end, sources):
    return fetch_raw_data_bundle(start, end, sources=sources)

assets = pd.read_csv('data/assets.csv')
area = json.loads(Path('data/service_area.geojson').read_text(encoding='utf-8'))
render_monitor_workspace(load_bundle, assets, area, {'weather', 'transport', 'gis'})
"""
            app = AppTest.from_string(code, default_timeout=30)
        else:
            app = AppTest.from_file('app.py', default_timeout=30)
            app.session_state['dashboard_authorised'] = True
            app.session_state['dashboard_page'] = 'Monitor'
        app.session_state['monitor_data_mode'] = 'Connected observations'
        for key, value in state.items():
            app.session_state[key] = value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_unverified_traffic_timezone_is_not_current(self):
        table = quality_table(observation_fixture(), pd.DataFrame(), pd.DataFrame())
        self.assertEqual(table[table['Source'].eq('Traffic 6806')].iloc[0]['State'], 'Timezone unverified')

    def check_views(self, bundle):
        app = self.app(bundle, dashboard_page='Overview')
        navigation = {widget.label for widget in app.button}
        self.assertTrue({'Overview', 'Monitor', 'Data'} <= navigation)
        self.assertFalse(any(widget.label in {'Workspace', 'View'} for widget in app.radio))
        next(widget for widget in app.button if widget.label == 'Monitor').click().run()
        self.assertFalse(app.exception)
        next(widget for widget in app.radio if widget.label == 'Data view').set_value('Connected observations').run()
        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.tabs], ['Readings', 'Connections', 'Results', 'Sources'])
        next(widget for widget in app.radio if widget.label == 'Time mode').set_value('Historical browsing').run()
        self.assertFalse(app.exception)
        self.assertFalse(next(widget for widget in app.date_input if widget.label == 'Observation dates').disabled)
        next(widget for widget in app.button if widget.label == 'Data').click().run()
        self.assertFalse(app.exception)
        next(widget for widget in app.button if widget.label == 'Overview').click().run()
        self.assertFalse(app.exception)

    def test_workspaces_with_observations(self):
        self.check_views(observation_fixture())

    def test_workspaces_when_apis_return_no_observations(self):
        bundle = empty_bundle()
        bundle['status'] = pd.DataFrame(columns=['connector_id', 'title', 'domain', 'status', 'records', 'last_call_utc', 'url', 'access_note'])
        self.check_views(bundle)

    def test_stale_water_is_not_labelled_unavailable_in_inspector(self):
        bundle = observation_fixture()
        bundle['water_levels']['date_time'] -= pd.Timedelta(days=1)
        app = self.app(bundle, standalone=True)
        self.assertTrue(any('<strong>Stale</strong>' in item.value for item in app.markdown))
        self.assertFalse(any('<strong>Unavailable</strong>' in item.value for item in app.markdown))

    def test_monitor_source_selection_loads_only_water(self):
        app = self.app(monitor_source_choice=['water_level'])
        self.assertTrue(any(widget.label == 'Observation sources' for widget in app.multiselect))
        self.assertEqual([call.kwargs['sources'] for call in self.fetch.call_args_list], [('water_level',)])

    def test_replay_cursor_changes_the_eight_point_window(self):
        app = self.app(standalone=True)
        next(widget for widget in app.checkbox if widget.label == 'Show observation replay').check().run()
        self.assertFalse(app.exception)
        cursor = next(widget for widget in app.slider if widget.label == 'Replay checkpoint')
        cursor.set_value(7).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('105' in item.value for item in app.caption))
        self.assertTrue(any('Checkpoint 8 / 12' in item.value for item in app.markdown))

    def test_partner_without_weather_access_cannot_load_water_or_replay(self):
        app = self.app(monitor_source_choice=['water_level'])
        next(widget for widget in app.selectbox if widget.label == 'Partner').set_value('Terminal operator').run()
        self.assertFalse(app.exception)
        self.assertTrue(any(widget.label == 'Observation sources' for widget in app.multiselect))
        sources = next(widget for widget in app.multiselect if widget.label == 'Observation sources')
        self.assertEqual(sources.options, ['Traffic counters'])
        self.assertFalse(any(widget.label == 'Show observation replay' for widget in app.checkbox))
        self.fetch.reset_mock()
        st.cache_data.clear()
        sources.set_value(['webtris']).run()
        self.assertFalse(app.exception)
        self.assertEqual([call.kwargs['sources'] for call in self.fetch.call_args_list], [('webtris',)])
        picker = next(widget for widget in app.selectbox if widget.label == 'Inspect an object')
        self.assertEqual(picker.options, ['Traffic counter 6806'])
        self.assertEqual(picker.value, 'traffic:6806')

    def test_map_freshness_matches_displayed_measurement_reference(self):
        bundle = observation_fixture()
        water = bundle['water_levels']
        fresh = water[water['station_reference'].eq('E70139')].copy()
        stale = fresh.assign(unit='m', datum_uri='datum:local', datum='Local datum',
                             date_time=fresh['date_time'] - pd.Timedelta(days=1))
        bundle['water_levels'] = pd.concat([stale, fresh])
        decks = []
        def capture(deck, **kwargs):
            decks.append(deck)
            return {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=capture):
            app = self.app(bundle, standalone=True)
        self.assertFalse(app.exception)
        points = next(layer.data for layer in decks[-1].layers if layer.id == 'monitoring-points')
        point = next(row for row in points if row['entity_id'] == 'water:E70139')
        self.assertEqual(point['unit'], 'mAOD')
        self.assertEqual(point['state'], 'Current')
        self.assertIn('|mAOD|', app.session_state['workbench_reference'])

    def test_connected_map_excludes_demo_assets_and_boundary_even_with_old_layer_state(self):
        decks = []
        def capture(deck, **kwargs):
            decks.append(deck)
            return {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=capture):
            app = self.app(standalone=True, workbench_layers={'demo': True}, workbench_layer_demo=True)
        self.assertFalse(app.exception)
        self.assertFalse(any(widget.label == 'Demonstration assets' for widget in app.checkbox))
        self.assertFalse(any(layer.id in {'service-area', 'demonstration-boundary'} for layer in decks[-1].layers))
        points = next(layer.data for layer in decks[-1].layers if layer.id == 'monitoring-points')
        self.assertTrue(all(not row['entity_id'].startswith('demo:') for row in points))


if __name__ == '__main__':
    unittest.main()
