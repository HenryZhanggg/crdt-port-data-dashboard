import unittest
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


class WeatherMapViewTests(unittest.TestCase):
    def app(self, views=('weather',), mode=None):
        now = pd.Timestamp.now(tz='UTC').floor('h')
        app = AppTest.from_string('''
import pandas as pd
import streamlit as st
from weather_map_views import render_weather_map

def load_bundle(start, end, sources):
    st.session_state['requested_sources'] = list(sources)
    return {'naptan': pd.DataFrame({'CommonName': ['Inside', 'Outside'],
        'Latitude': [53.45, 53.8], 'Longitude': [-3.01, -3.01]})}

render_weather_map(st.session_state['snapshot'], load_bundle, st.session_state['views'])
''')
        app.session_state['views'] = set(views)
        app.session_state['snapshot'] = {
            'place': {'lat': 53.448, 'lon': -3.015},
            'weather': {'status': 'available', 'source_name': 'MET Norway',
                'source_url': 'https://api.met.no/weatherapi/locationforecast/2.0/documentation',
                'rows': [{'time': (now+pd.Timedelta(hours=offset)).isoformat(), 'rain_mm': rain,
                          'temp_c': 12, 'wind_m_s': 4}
                         for offset, rain in [(-1, 100), (1, 0.0), (2, 2.5)]]},
            'flood_warnings': {'status': 'available', 'source_name': 'Environment Agency',
                'source_url': 'https://environment.data.gov.uk/flood-monitoring/doc/reference',
                'items': []},
        }
        if mode:
            app.session_state['monitor_map_layer'] = mode
        return app.run()

    def test_no_selection_starts_with_a_plain_map_and_no_provider_work(self):
        with patch('streamlit.pydeck_chart', return_value={}) as chart, \
                patch('daily_service.load_flood_area_geometry') as geometry:
            app = self.app()
            self.assertFalse(app.exception)
            self.assertEqual(chart.call_args.args[0].layers, [])
            self.assertFalse(app.selectbox)
            self.assertTrue({'Wind','Rain','Flood areas','Water levels'} <= {btn.label for btn in app.button})
            geometry.assert_not_called()

    def test_reselecting_a_layer_clears_the_overlay(self):
        with patch('streamlit.pydeck_chart', return_value={}) as chart:
            app = self.app()
            app.button(key='monitor_layer_Rain').click().run()
            self.assertFalse(app.exception)
            self.assertIn('weather-grid',[layer.id for layer in chart.call_args.args[0].layers])
            app.button(key='monitor_layer_Rain').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(chart.call_args.args[0].layers, [])

    def test_reference_area_and_optional_transport_points_keep_scope_and_permissions(self):
        boundary = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [[[-3.02, 53.44], [-3.00, 53.44],
                [-3.00, 53.46], [-3.02, 53.46], [-3.02, 53.44]]]}, 'properties': {}}]}
        with patch('daily_views._map') as render_map, \
                patch('daily_service.load_flood_area_geometry', return_value={'geojson': boundary}) as geometry:
            app = self.app(mode='Flood areas')
            self.assertFalse(app.exception)
            self.assertFalse(app.checkbox)
            self.assertNotIn('requested_sources', app.session_state)
            self.assertTrue(render_map.call_args.kwargs['focus']['reference'])
            geometry.assert_called_with('013WATMEWLW')
            app = self.app(('weather', 'transport'), mode='Flood areas')
            self.assertNotIn('requested_sources', app.session_state)
            app.checkbox[0].check().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['requested_sources'], ['naptan'])
            self.assertEqual([stop['name'] for stop in render_map.call_args.kwargs['focus']['stops']], ['Inside'])

    def test_switching_layers_replaces_the_grid_and_arrows(self):
        with patch('streamlit.pydeck_chart', return_value={}) as chart:
            app = self.app()
            app.button(key='monitor_layer_Wind').click().run()
            self.assertFalse(app.exception)
            self.assertEqual([layer.id for layer in chart.call_args.args[0].layers],
                             ['weather-grid', 'weather-wind-shafts', 'weather-wind-heads'])
            self.assertTrue(any('10 m wind' in item.value for item in app.caption))
            app.button(key='monitor_layer_Rain').click().run()
            self.assertFalse(app.exception)
            self.assertEqual([layer.id for layer in chart.call_args.args[0].layers], ['weather-grid'])

    def test_map_pick_updates_exact_cell_and_clear_removes_it(self):
        import weather_layers
        cell = weather_layers.grid_layers('Rain', weather_layers.load_grid('Rain'))[0][0].data[12]
        selection = {'selection': {'objects': {'weather-grid': [{'id': cell['id']}]}}}
        with patch('streamlit.pydeck_chart', return_value=selection):
            app = self.app(mode='Rain')
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox[0].value, cell['id'])
            self.assertEqual(app.metric[0].value, cell['value'])
            app.button(key='monitor_layer_Rain').click().run()
            self.assertFalse(app.exception)
            self.assertFalse(app.selectbox)
            self.assertFalse(app.metric)

    def test_archive_is_dated_and_exposes_a_keyboard_accessible_exact_cell_value(self):
        app = self.app(mode='Rain')
        self.assertFalse(app.exception)
        self.assertTrue(any('14 Nov 2025' in item.value for item in app.caption))
        cells = app.selectbox[0]
        self.assertEqual(len(cells.options), 169)
        self.assertFalse(app.metric)
        sample = json.loads((Path(__file__).resolve().parent.parent/'data/ukv_liverpool_rain_sample.json').read_text(encoding='utf-8'))
        cell = sample['cells'][1]
        cells.set_value(f"rain:{cell['row']}:{cell['col']}").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, f"{cell['mm']:g} mm / 1h")
        self.assertEqual(len(app.get('deck_gl_json_chart')),1)


if __name__ == '__main__':
    unittest.main()
