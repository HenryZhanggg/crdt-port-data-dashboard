import importlib.util
import unittest
from unittest.mock import patch

import pandas as pd


class WorkspaceLinksTests(unittest.TestCase):
    def links(self):
        self.assertIsNotNone(importlib.util.find_spec('workspace_links'), 'Cross-page observation context is required')
        import workspace_links
        return workspace_links

    def series(self, **updates):
        return dict({'id': 'gauge:a', 'station_reference': 'E70139', 'unit': 'mAOD',
            'datum_uri': 'datum:aod', 'rows': [{'time': '2026-10-01T23:00:00-02:00'},
                {'time': '2026-10-12T04:00:00Z'}]}, **updates)

    def test_explicit_station_and_exact_reference_use_returned_utc_window(self):
        context = self.links().water_handoff_context(self.series())
        self.assertEqual(context['entity_id'], 'water:E70139')
        self.assertEqual((context['station_reference'], context['unit'], context['datum_uri']),
                         ('E70139', 'mAOD', 'datum:aod'))
        self.assertEqual((context['start'], context['end']), ('2026-10-06', '2026-10-12'))

    def test_cached_composite_id_is_supported_without_name_or_coordinate_guessing(self):
        links = self.links()
        series = self.series(id='water:E70124|m|datum:local')
        series.pop('station_reference')
        series.update(unit='m', datum_uri='datum:local')
        self.assertEqual(links.water_handoff_context(series)['station_reference'], 'E70124')
        series['id'] = 'gauge:b'
        series.update(name='E70124 Liverpool', lat=53.448, lon=-3.015)
        self.assertIsNone(links.water_handoff_context(series))

    def test_invalid_or_absent_returned_times_do_not_create_handoff(self):
        links = self.links()
        self.assertIsNone(links.water_handoff_context(None))
        self.assertIsNone(links.water_handoff_context(self.series(rows=[])))
        self.assertIsNone(links.water_handoff_context(self.series(rows=[{'time': 'unknown'}])))

    def test_returned_window_accepts_mixed_timestamp_precision(self):
        context=self.links().water_handoff_context(self.series(rows=[
            {'time':'2026-10-02T01:00:00Z'},{'time':'2026-10-04T12:00:00.123456Z'}]))
        self.assertEqual((context['start'],context['end']),('2026-10-02','2026-10-04'))

    def test_future_only_series_has_no_handoff_and_future_rows_do_not_extend_window(self):
        links=self.links()
        now=pd.Timestamp.now(tz='UTC')
        future=(now+pd.Timedelta(days=2)).isoformat()
        valid=(now-pd.Timedelta(days=1)).isoformat()
        self.assertIsNone(links.water_handoff_context(self.series(rows=[{'time':future}])))
        context=links.water_handoff_context(self.series(rows=[{'time':valid},{'time':future}]))
        self.assertEqual(context['end'],(now-pd.Timedelta(days=1)).date().isoformat())

    def test_open_water_sets_only_monitor_state_and_resets_native_pick(self):
        links = self.links()
        state = {'daily_place_id': 'gauge:b', 'workbench_map_revision': 3,
                 'workbench_last_map_id': 'traffic:6806','workbench_layer_water':False,
                 'workbench_layers':{'water':False,'traffic':False}}
        with patch.object(links.st, 'session_state', state):
            links.open_water_observations(self.series())
        self.assertEqual(state['dashboard_page'], 'Monitor')
        self.assertEqual(state['monitor_data_mode'], 'Connected observations')
        self.assertEqual(state['workbench_reference'], 'E70139|mAOD|datum:aod')
        self.assertEqual(state['workbench_map_revision'], 4)
        self.assertIsNone(state['workbench_last_map_id'])
        self.assertEqual(state['daily_place_id'], 'gauge:b')
        self.assertEqual(state['monitor_source_choice'], ['water_level'])
        self.assertTrue(state['workbench_layer_water'])
        self.assertEqual(state['workbench_layers'],{'water':True,'traffic':False})

    def test_filter_preserves_exact_reference_dates_and_does_not_mutate_cache(self):
        links = self.links()
        water = pd.DataFrame([
            {'station_reference': station, 'unit': unit, 'datum_uri': datum,
             'date_time': time, 'value': 1}
            for station, unit, datum in [('E70139', 'mAOD', 'datum:aod'),
                ('E70139', 'm', 'datum:local'), ('E70124', 'mAOD', 'datum:aod')]
            for time in ['2026-10-05T12:00:00Z', '2026-10-12T12:00:00Z']])
        bundle = {'water_levels': water, 'webtris_daily': pd.DataFrame({'site_id': ['6806']})}
        original = water.copy(deep=True)
        result = links.filter_context_bundle(bundle, links.water_handoff_context(self.series()))
        self.assertEqual(len(result['water_levels']), 1)
        self.assertEqual(result['water_levels'].iloc[0]['datum_uri'], 'datum:aod')
        self.assertTrue(result['webtris_daily'].empty)
        pd.testing.assert_frame_equal(water, original)

    def test_data_handoff_initialises_source_tab_scope_and_historical_dates(self):
        links = self.links()
        context = links.water_handoff_context(self.series())
        state = {'data_source_search': 'stale search', 'daily_place_id': 'gauge:a'}
        with patch.object(links.st, 'session_state', state):
            links.open_data_context(context, 'Quality')
        self.assertEqual(state['dashboard_page'], 'Data')
        self.assertEqual(state['data_workspace_tab'], 'Quality')
        self.assertEqual(state['data_quality_scope'], 'Water levels')
        self.assertEqual(state['data_source_id'], 'HS004')
        self.assertEqual(state['data_table_HS004'], 'water_levels')
        self.assertEqual(state['data_source_search'], '')
        self.assertEqual(state['data_preview_dates_Historical browsing'],
                         state['data_quality_dates_Historical browsing'])

    def test_measure_context_filters_before_selection_and_retains_failed_request(self):
        links = self.links()
        context = links.water_handoff_context(self.series(measure_uri='https://example.org/measure/b'))
        self.assertEqual(context.get('measure_uri'), 'https://example.org/measure/b')
        frame = pd.DataFrame([
            dict(station_reference='E70139', unit='mAOD', datum_uri='datum:aod',
                 date_time='2026-10-12T12:00:00Z', measure_uri=uri)
            for uri in ('https://example.org/measure/a', 'https://example.org/measure/b')])
        bundle = {'water_levels': frame, 'status': pd.DataFrame([
            {'connector_id': 'water_level_api', 'status': 'api_error'},
            {'connector_id': 'webtris_sites_api', 'status': 'api_connected'}])}
        scoped = links.filter_context_bundle(bundle, context)
        self.assertEqual(scoped['water_levels']['measure_uri'].tolist(), [context['measure_uri']])
        self.assertEqual(scoped['status']['connector_id'].tolist(), ['water_level_api'])
        missing = links.filter_context_bundle(bundle, {**context, 'measure_uri': 'https://example.org/measure/absent'})
        self.assertTrue(missing['water_levels'].empty)
        self.assertEqual(len(frame), 2)


if __name__ == '__main__':
    unittest.main()
