import importlib.util
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from test_dashboard_views import observation_fixture


APP = '''
import streamlit as st
import pandas as pd
from monitor_workspace import render_monitor_workspace
from test_dashboard_views import observation_fixture
def load_bundle(start, end, sources):
    st.session_state['requested_sources'] = sources
    st.session_state['load_count'] = st.session_state.get('load_count', 0) + 1
    return observation_fixture()
def refresh(*args):
    st.session_state['refresh_count'] = st.session_state.get('refresh_count', 0) + 1
    st.session_state['refresh_args'] = args
render_monitor_workspace(load_bundle, pd.DataFrame(), {}, st.session_state.get('allowed_views'), refresh=refresh)
'''


class MonitorWorkspaceTests(unittest.TestCase):
    def app(self, **state):
        self.assertIsNotNone(importlib.util.find_spec('monitor_workspace'), 'Monitor workspace module is required')
        app = AppTest.from_string(APP, default_timeout=30)
        for key, value in state.items():
            app.session_state[key] = value
        app.run()
        self.assertFalse(app.exception)
        return app

    def connected(self, **state):
        return self.app(monitor_data_mode='Connected observations', **state)

    def handoff(self, **changes):
        from workspace_links import open_water_observations
        rows = observation_fixture()['water_levels']
        rows = rows[rows['station_reference'].eq('E70124')]
        series = {'station_reference': 'E70124', 'unit': 'm',
            'datum_uri': 'https://example.org/test/local-datum',
            'rows': [{'time': str(value)} for value in rows['date_time']]}
        series.update(changes)
        state = {}
        with patch('workspace_links.st.session_state', state):
            open_water_observations(series)
        return state

    def test_overview_handoff_selects_exact_water_reference_and_returned_dates(self):
        state = self.handoff()
        app = self.app(**state)
        self.assertEqual(app.session_state['requested_sources'], ('water_level',))
        self.assertEqual(app.session_state['workbench_entity_id'], 'water:E70124')
        self.assertEqual(app.session_state['workbench_reference'], 'E70124|m|https://example.org/test/local-datum')
        self.assertEqual(app.session_state['monitor_start'], state['monitor_handoff']['start'])
        self.assertEqual(app.session_state['monitor_end'], state['monitor_handoff']['end'])
        self.assertTrue(any(x.label == 'View data source' for x in app.button))
        self.assertTrue(any(x.label == 'Check data quality' for x in app.button))

    def test_missing_handoff_datum_does_not_fall_back_to_other_reference(self):
        app = self.app(**self.handoff(datum_uri='datum:not-returned'))
        self.assertTrue(any('requested measurement reference' in x.value.lower() for x in app.info))
        self.assertFalse(any(x.label == 'Download selected observations' for x in app.get('download_button')))
        self.assertEqual(app.session_state['workbench_reference'], 'E70124|m|datum:not-returned')
        next(x for x in app.button if x.label == 'Clear context and choose observations').click().run()
        self.assertFalse(app.exception)
        self.assertNotIn('monitor_handoff', app.session_state)
        self.assertTrue(any(x.label == 'Inspect an object' for x in app.selectbox))

    def test_changed_permissions_do_not_query_handoff_family(self):
        app = self.app(allowed_views={'transport'}, **self.handoff())
        self.assertNotIn('load_count', app.session_state)
        self.assertTrue(any('outside this partner view' in x.value for x in app.info))

    def test_manual_object_choice_clears_handoff(self):
        app = self.app(**self.handoff())
        next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('water:E70139').run()
        self.assertFalse(app.exception)
        self.assertNotIn('monitor_handoff', app.session_state)
        self.assertEqual(app.session_state['workbench_entity_id'], 'water:E70139')

    def test_native_map_pick_clears_handoff_and_stays_selected_on_next_rerun(self):
        app=self.app(**self.handoff())
        event={'selection':{'objects':{'monitoring-points':[{'entity_id':'water:E70139'}]}}}
        with patch('streamlit.pydeck_chart',return_value=event):
            app.run()
        self.assertFalse(app.exception)
        self.assertNotIn('monitor_handoff',app.session_state)
        self.assertEqual(app.session_state['workbench_entity_id'],'water:E70139')
        app.run()
        self.assertEqual(app.session_state['workbench_entity_id'],'water:E70139')

    def test_manual_measurement_reference_clears_handoff(self):
        bundle=observation_fixture()
        alternate=bundle['water_levels'][bundle['water_levels']['station_reference'].eq('E70124')].assign(datum_uri='datum:alternate')
        bundle['water_levels']=pd.concat([bundle['water_levels'],alternate],ignore_index=True)
        with patch('test_dashboard_views.observation_fixture',return_value=bundle):
            app=self.app(**self.handoff())
            next(x for x in app.selectbox if x.label=='Measurement reference').set_value('E70124|m|datum:alternate').run()
        self.assertFalse(app.exception)
        self.assertNotIn('monitor_handoff',app.session_state)
        self.assertEqual(app.session_state['workbench_reference'],'E70124|m|datum:alternate')

    def test_data_quality_action_carries_monitor_reference_and_period(self):
        app = self.app(**self.handoff())
        next(x for x in app.button if x.label == 'Check data quality').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['dashboard_page'], 'Data')
        self.assertEqual(app.session_state['data_workspace_tab'], 'Quality')
        self.assertEqual(app.session_state['data_handoff']['station_reference'], 'E70124')
        self.assertEqual(app.session_state['data_handoff']['datum_uri'], 'https://example.org/test/local-datum')
        self.assertEqual((app.session_state['data_handoff']['start'], app.session_state['data_handoff']['end']),
                         (app.session_state['monitor_start'], app.session_state['monitor_end']))

    def test_data_roundtrip_from_both_sources_keeps_missing_reference_explicit(self):
        app=self.connected()
        next(x for x in app.selectbox if x.label=='Inspect an object').set_value('water:E70124').run()
        next(x for x in app.button if x.label=='View data source').click().run()
        bundle=observation_fixture()
        bundle['water_levels']=bundle['water_levels'][bundle['water_levels']['station_reference'].eq('E70139')]
        with patch('test_dashboard_views.observation_fixture',return_value=bundle):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['requested_sources'],('water_level','webtris'))
        self.assertTrue(any('requested measurement reference' in x.value.lower() for x in app.info))
        self.assertFalse(any(x.label=='Download selected observations' for x in app.get('download_button')))
        self.assertEqual(app.session_state['workbench_entity_id'],'water:E70124')

    def test_manual_dates_clear_return_context_without_changing_source_choices(self):
        app=self.connected()
        next(x for x in app.radio if x.label=='Time mode').set_value('Historical browsing').run()
        next(x for x in app.button if x.label=='View data source').click().run()
        self.assertIn('monitor_handoff',app.session_state)
        dates=next(x for x in app.date_input if x.label=='Observation dates')
        first,last=dates.value
        dates.set_value((first+pd.Timedelta(days=1),last)).run()
        self.assertFalse(app.exception)
        self.assertNotIn('monitor_handoff',app.session_state)
        self.assertEqual(app.session_state['requested_sources'],('water_level','webtris'))

    def test_empty_traffic_period_still_explains_historical_publication_delay(self):
        bundle=observation_fixture()
        bundle['webtris_daily']=bundle['webtris_daily'].iloc[:0]
        with patch('test_dashboard_views.observation_fixture',return_value=bundle):
            app=self.connected()
            next(x for x in app.selectbox if x.label=='Inspect an object').set_value('traffic:6806').run()
        self.assertTrue(any('one month after collection' in x.value for x in app.caption))

    def test_example_does_not_request_sources_and_has_one_context(self):
        app = self.app()
        self.assertNotIn('load_count', app.session_state)
        self.assertEqual(next(x for x in app.radio if x.label == 'Data view').options,
                         ['Example network', 'Connected observations'])
        self.assertFalse(any(x.label in {'Content mode', 'Spatial view', 'Network data'} for x in app.radio))
        self.assertFalse(app.date_input)
        self.assertFalse(any(x.label in {'Run model', 'View illustrative results'} for x in app.button))
        self.assertEqual([x.label for x in app.tabs], ['Readings', 'Connections', 'Results', 'Sources'])

    def test_connected_observations_share_map_object_reference_and_tabs(self):
        app = self.connected()
        self.assertEqual(app.session_state['requested_sources'], ('water_level', 'webtris'))
        self.assertEqual([x.label for x in app.tabs], ['Readings', 'Connections', 'Results', 'Sources'])
        self.assertTrue(any(x.label == 'Measurement reference' for x in app.selectbox))
        self.assertTrue(any(x.label == 'Visible observation interval' for x in app.select_slider))
        self.assertTrue(any(x.label == 'Download selected observations' for x in app.get('download_button')))
        self.assertFalse(any(x.label in {'Visible panels', 'Demonstration assets'} for x in list(app.multiselect) + list(app.checkbox)))

    def test_partner_permissions_limit_source_requests(self):
        app = self.connected(allowed_views={'transport'})
        self.assertEqual(app.session_state['requested_sources'], ('webtris',))
        self.assertEqual(app.session_state['workbench_entity_id'], 'traffic:6806')
        self.assertFalse(any(x.label == 'Measurement reference' for x in app.selectbox))

    def test_history_larger_than_seven_days_never_loads(self):
        today = pd.Timestamp.now(tz='UTC').date()
        app = self.connected(monitor_mode='Historical browsing',
                             **{'monitor_dates_Historical browsing': (today - pd.Timedelta(days=9), today)})
        self.assertNotIn('load_count', app.session_state)
        self.assertTrue(any('seven days' in x.value for x in app.info))

    def test_refresh_uses_supplied_callback(self):
        app = self.connected()
        next(x for x in app.button if x.label == 'Refresh data').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['refresh_count'], 1)
        self.assertEqual(app.session_state['refresh_args'],
                         (('water_level', 'webtris'), app.session_state['monitor_start'], app.session_state['monitor_end']))

    def test_real_selection_survives_example_switch(self):
        app = self.connected()
        next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('traffic:6806').run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Example network').run()
        next(x for x in app.button if x.key == 'semantic_object_demo:gauge_a').click().run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Connected observations').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'], 'traffic:6806')
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:gauge_a')

    def test_map_pick_selects_traffic_and_keeps_source_timezone(self):
        event = {'selection': {'objects': {'monitoring-points': [{'entity_id': 'traffic:6806'}]}}}
        with patch('streamlit.pydeck_chart', return_value=event):
            app = self.connected()
        self.assertEqual(app.session_state['workbench_entity_id'], 'traffic:6806')
        self.assertTrue(any('Timezone unverified' in str(x.value) for x in app.markdown))
        self.assertTrue(any(x.label == 'Traffic counters' for x in app.multiselect))

    def test_observation_source_choice_survives_example_mode(self):
        app = self.connected()
        next(x for x in app.multiselect if x.label == 'Observation sources').set_value(['water_level']).run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Example network').run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Connected observations').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['requested_sources'], ('water_level',))

    def test_water_interval_filters_export_and_keeps_reference(self):
        with patch('streamlit.download_button') as download:
            app = self.connected()
            slider = next(x for x in app.select_slider if x.label == 'Visible observation interval')
            times = observation_fixture()['water_levels']['date_time'].drop_duplicates().tolist()
            slider.set_value((times[2], times[5])).run()
        export = next(call for call in reversed(download.call_args_list) if call.args[0] == 'Download selected observations')
        from io import BytesIO
        rows = pd.read_csv(BytesIO(export.args[1]))
        self.assertEqual(len(rows), 4)
        self.assertEqual(set(rows['station_reference']), {'E70139'})
        self.assertEqual(set(rows['datum']), {'Ordnance Datum Newlyn'})
        self.assertEqual(pd.to_datetime(rows['date_time'], utc=True).tolist(), times[2:6])

    def test_published_run_outputs_follow_selected_object(self):
        from module_contracts import package_template, validate_package
        run = package_template('model_run')
        run['outputs'] = [dict(run['outputs'][0], entity_id='water:E70139'),
                          dict(run['outputs'][0], entity_id='traffic:6806', value=42)]
        run = validate_package(run)
        app = self.connected(partner_runs={run['run_id']: run}, current_run_id=run['run_id'])
        results = next(tab for tab in app.tabs if tab.label == 'Results')
        outputs = next(frame.value for frame in results.dataframe if 'entity_id' in frame.value)
        self.assertEqual(outputs['entity_id'].tolist(), ['water:E70139'])

    def test_imported_dependencies_keep_real_endpoints_and_evidence_separate(self):
        from module_contracts import package_template, validate_package
        package = package_template('dependencies')
        package['relationships'][0].update(source_id='water:E70139', target_id='traffic:6806',
                                            evidence_ref='provider:dependency-note')
        package = validate_package(package)
        with patch('streamlit.pydeck_chart', return_value={'selection': {}}) as chart:
            app = self.connected(dependency_package=package)
        connections = next(tab for tab in app.tabs if tab.label == 'Connections')
        rows = next(frame.value for frame in connections.dataframe if 'source_id' in frame.value)
        self.assertEqual(rows.iloc[0]['source_id'], 'water:E70139')
        self.assertEqual(rows.iloc[0]['target_id'], 'traffic:6806')
        self.assertEqual(rows.iloc[0]['evidence_ref'], 'provider:dependency-note')
        self.assertEqual(rows.iloc[0]['Endpoint alignment'], 'Both in workspace')
        self.assertFalse(any(layer.id.startswith('semantic_') for layer in chart.call_args.args[0].layers))

    def test_selected_object_quality_excludes_other_observation_families(self):
        app = self.connected()
        for entity_id, prefix in [('water:E70139', 'Water '), ('traffic:6806', 'Traffic ')]:
            with self.subTest(entity_id=entity_id):
                next(x for x in app.selectbox if x.label == 'Inspect an object').set_value(entity_id).run()
                self.assertFalse(app.exception)
                sources = next(tab for tab in app.tabs if tab.label == 'Sources')
                table = next(frame.value for frame in sources.dataframe if {'Source', 'Kind', 'State'} <= set(frame.value))
                observations = table[table['Kind'].eq('Observation')]
                self.assertFalse(observations.empty)
                self.assertTrue(observations['Source'].str.startswith(prefix).all(), observations.to_string())

    def test_traffic_chart_follows_inspector_and_keeps_optional_comparisons(self):
        bundle = observation_fixture()
        bundle['webtris_sites'] = pd.concat([bundle['webtris_sites'],
            bundle['webtris_sites'].assign(site_id='6807')], ignore_index=True)
        bundle['webtris_daily'] = pd.concat([bundle['webtris_daily'],
            bundle['webtris_daily'].assign(site_id='6807', **{'Total Volume': 900})], ignore_index=True)
        figures = {}
        def capture(figure, **kwargs):
            figures[kwargs.get('key')] = figure
        with patch('test_dashboard_views.observation_fixture', return_value=bundle), patch('streamlit.plotly_chart', side_effect=capture):
            app = self.connected()
            next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('traffic:6806').run()
            self.assertEqual([trace.name for trace in figures['monitor_traffic_Total Volume'].data], ['6806'])
            next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('traffic:6807').run()
            self.assertFalse(app.exception)
            self.assertEqual([trace.name for trace in figures['monitor_traffic_Total Volume'].data], ['6807'])
            self.assertTrue(all(value == 900 for value in figures['monitor_traffic_Total Volume'].data[0].y))
            next(x for x in app.multiselect if x.label == 'Traffic counters').set_value(['6806']).run()
            self.assertEqual({trace.name for trace in figures['monitor_traffic_Total Volume'].data}, {'6806', '6807'})

    def test_water_reference_and_map_stay_aligned_through_source_changes(self):
        bundle = observation_fixture()
        original = bundle['water_levels'][bundle['water_levels']['station_reference'].eq('E70139')]
        alternate = original.assign(unit='m', datum='Alternate local reference', datum_uri='datum:alternate',
                                    date_time=original['date_time'] - pd.Timedelta(hours=4))
        bundle['water_levels'] = pd.concat([bundle['water_levels'], alternate], ignore_index=True)
        decks = []
        def capture(deck, **kwargs):
            decks.append(deck)
            return {'selection': {}}
        with patch('test_dashboard_views.observation_fixture', return_value=bundle), patch('streamlit.pydeck_chart', side_effect=capture):
            app = self.connected()
            next(x for x in app.selectbox if x.label == 'Measurement reference').set_value('E70139|m|datum:alternate').run()
            next(x for x in app.multiselect if x.label == 'Observation sources').set_value(['webtris']).run()
            self.assertEqual(app.session_state['workbench_entity_id'], 'traffic:6806')
            next(x for x in app.multiselect if x.label == 'Observation sources').set_value(['water_level', 'webtris']).run()
            next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('water:E70139').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_reference'], 'E70139|m|datum:alternate')
        points = next(layer.data for layer in decks[-1].layers if layer.id == 'monitoring-points')
        point = next(row for row in points if row['entity_id'] == 'water:E70139')
        self.assertEqual(point['datum_uri'], 'datum:alternate')
        self.assertEqual(point['unit'], 'm')


if __name__ == '__main__':
    unittest.main()
