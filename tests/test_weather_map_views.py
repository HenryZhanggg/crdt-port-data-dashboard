import unittest
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


class WeatherMapViewTests(unittest.TestCase):
    def app(self, views=('weather',), mode=None, focus=None):
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
            app.session_state['weather_map_mode'] = mode
        if focus:
            app.session_state['daily_map_focus'] = focus
        return app.run()

    def test_live_rain_uses_selected_future_hour_at_forecast_point(self):
        with patch('weather_map_views._archive_sample', return_value=None), patch('daily_views._map') as render_map:
            app = self.app()
            self.assertFalse(app.exception)
            hour = next(widget for widget in app.selectbox if widget.label == 'Forecast hour (UTC)')
            self.assertEqual(len(hour.options), 2)
            self.assertEqual(render_map.call_args.kwargs['focus']['rain']['rain_mm'], 0.0)
            next_hour = (pd.Timestamp(hour.value)+pd.Timedelta(hours=1)).isoformat()
            hour.set_value(next_hour).run()
            self.assertFalse(app.exception)
            self.assertEqual(render_map.call_args.kwargs['focus']['rain']['rain_mm'], 2.5)

    def test_reference_area_and_optional_transport_points_keep_scope_and_permissions(self):
        boundary = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
            'geometry': {'type': 'Polygon', 'coordinates': [[[-3.02, 53.44], [-3.00, 53.44],
                [-3.00, 53.46], [-3.02, 53.46], [-3.02, 53.44]]]}, 'properties': {}}]}
        with patch('weather_map_views._archive_sample', return_value=None), patch('daily_views._map') as render_map, \
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

    def test_overview_handoff_opens_the_selected_forecast_hour(self):
        chosen = (pd.Timestamp.now(tz='UTC').floor('h')+pd.Timedelta(hours=2)).isoformat()
        with patch('weather_map_views._archive_sample', return_value=None), patch('daily_views._map') as render_map:
            app = self.app(mode='Flood areas',focus=('rain',chosen))
            self.assertFalse(app.exception)
            self.assertEqual(app.radio[0].value,'Rain forecast')
            self.assertEqual(render_map.call_args.kwargs['focus']['rain']['rain_mm'],2.5)

    def test_expired_overview_hour_requires_an_explicit_new_choice(self):
        with patch('daily_views._map') as render_map:
            app = self.app(focus=('rain','2025-11-14T17:00:00+00:00'))
        self.assertFalse(app.exception)
        self.assertTrue(any('selected hour is no longer' in item.value for item in app.info))
        self.assertIsNone(render_map.call_args.kwargs['focus'])

    def test_previous_warning_area_keeps_exact_boundary_as_reference(self):
        with patch('daily_views._map'), patch('daily_service.load_flood_area_geometry',
                return_value={'geojson':None}) as geometry:
            app = self.app(focus=('flood','013FWBSEAFORTH'))
        self.assertFalse(app.exception)
        geometry.assert_called_once_with('013FWBSEAFORTH')
        self.assertEqual(app.selectbox[0].value,'013FWBSEAFORTH')

    def test_archive_is_dated_and_exposes_a_keyboard_accessible_exact_cell_value(self):
        app = self.app(mode='Archived rainfall grid')
        self.assertFalse(app.exception)
        self.assertTrue(any('14 Nov 2025' in item.value for item in app.caption))
        cells = app.selectbox[0]
        self.assertEqual(len(cells.options),169)
        cells.set_value(1).run()
        self.assertFalse(app.exception)
        sample = json.loads((Path(__file__).resolve().parent.parent/'data/ukv_liverpool_rain_sample.json').read_text(encoding='utf-8'))
        self.assertEqual(app.metric[0].value,f"{sample['cells'][1]['mm']:.3f} mm")
        self.assertEqual(len(app.get('deck_gl_json_chart')),1)


if __name__ == '__main__':
    unittest.main()
