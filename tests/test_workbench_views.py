import unittest
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from api_connectors import empty_bundle
from module_contracts import package_template, validate_package
from test_dashboard_views import observation_fixture


class WorkbenchViewTests(unittest.TestCase):
    def app(self, bundle=None):
        st.cache_data.clear()
        self.fetch = patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture() if bundle is None else bundle)
        self.fetch.start()
        self.addCleanup(self.fetch.stop)
        app = AppTest.from_string('''
import pandas as pd
from api_connectors import fetch_raw_data_bundle
from monitor_workspace import render_monitor_workspace
def load_bundle(start, end, sources):
    return fetch_raw_data_bundle(start, end, sources=sources)
render_monitor_workspace(load_bundle, pd.DataFrame(), {})
''', default_timeout=30)
        app.session_state['monitor_data_mode'] = 'Connected observations'
        return app.run()

    def results_app(self, runs, current=None):
        app = AppTest.from_string('from workbench_views import render_runs\nrender_runs()', default_timeout=30)
        app.session_state['partner_runs'] = runs
        if current is not None:
            app.session_state['current_run_id'] = current
        return app.run()

    def test_monitor_has_shared_inspector_and_fixed_detail_tabs(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(any('SPATIAL SITUATION' in x.value for x in app.markdown))
        self.assertTrue(any(x.label == 'Inspect an object' for x in app.selectbox))
        self.assertEqual([tab.label for tab in app.tabs], ['Readings', 'Connections', 'Results', 'Sources'])
        self.assertFalse(any(x.label == 'Visible panels' for x in app.multiselect))

    def test_recent_observations_are_a_query_window_and_history_keeps_date_control(self):
        app = self.app()
        mode = next(x for x in app.radio if x.label == 'Time mode')
        self.assertEqual(mode.value, 'Recent observations')
        self.assertTrue(app.date_input[0].disabled)
        mode.set_value('Historical browsing').run()
        self.assertFalse(app.exception)
        self.assertFalse(app.date_input[0].disabled)
        self.assertTrue(any(x.label == 'Inspect an object' for x in app.selectbox))

    def test_map_click_on_traffic_opens_the_same_object_in_inspector(self):
        selection = {'selection': {'objects': {'monitoring-points': [{'entity_id': 'traffic:6806'}]}}}
        with patch('streamlit.pydeck_chart', return_value=selection):
            app = self.app()
        self.assertFalse(app.exception)
        self.assertIn('workbench_entity_id', app.session_state)
        self.assertEqual(app.session_state['workbench_entity_id'], 'traffic:6806')
        self.assertTrue(any('Timezone unverified' in str(x.value) for x in app.markdown))

    def test_map_label_pick_opens_the_corresponding_object(self):
        selection = {'selection': {'objects': {'monitoring-labels': [{'entity_id': 'water:E70124'}]}}}
        with patch('streamlit.pydeck_chart', return_value=selection):
            app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'], 'water:E70124')

    def test_manual_inspector_choice_clears_previous_native_map_selection(self):
        keys, decks = [], []
        def capture(deck, **kwargs):
            keys.append(kwargs['key'])
            decks.append(deck)
            return {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=capture):
            app = self.app()
            previous_key = keys[-1]
            next(x for x in app.selectbox if x.label == 'Inspect an object').set_value('water:E70124').run()
        self.assertFalse(app.exception)
        self.assertNotEqual(keys[-1], previous_key)
        ring = next(layer for layer in decks[-1].layers if layer.id == 'selected-object')
        self.assertEqual(ring.data[0]['entity_id'], 'water:E70124')

    def test_monitor_is_usable_without_partner_models(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(any('No published run packages' in str(x.value) for x in app.caption))
        self.assertTrue(any('No WP4 dependency package' in str(x.value) for x in app.info))
        self.assertFalse(app.file_uploader)

    def test_empty_feeds_do_not_create_assets_or_impact_results(self):
        app = self.app(empty_bundle())
        self.assertFalse(app.exception)
        self.assertIn('workbench_entity_id', app.session_state)
        self.assertIsNone(app.session_state['workbench_entity_id'])
        self.assertTrue(any('No monitoring objects' in str(x.value) for x in app.info))

    def test_example_assets_have_their_own_mode_and_selection(self):
        app = self.app()
        self.assertFalse(any(x.label == 'Demonstration assets' for x in app.checkbox))
        real_id = app.session_state['workbench_entity_id']
        next(x for x in app.radio if x.label == 'Data view').set_value('Example network').run()
        next(x for x in app.button if x.key == 'semantic_object_demo:road_a').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'], real_id)
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:road_a')

    def test_password_gate_prevents_loading_data(self):
        st.cache_data.clear()
        with patch('api_connectors.fetch_raw_data_bundle') as fetch:
            app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertFalse(app.exception)
        fetch.assert_not_called()
        self.assertFalse(any(x.label == 'Visible panels' for x in app.multiselect))

    def test_map_and_inspector_follow_the_same_reference(self):
        bundle = observation_fixture()
        fresh = bundle['water_levels'][bundle['water_levels']['station_reference'].eq('E70139')].copy()
        old = fresh.assign(unit='m', datum='Old local reference', datum_uri='datum:old',
                           date_time=fresh['date_time'] - pd.Timedelta(days=1))
        bundle['water_levels'] = pd.concat([old, fresh], ignore_index=True)
        decks = []
        def capture(deck, **kwargs):
            decks.append(deck)
            return {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=capture):
            app = self.app(bundle)
            self.assertFalse(app.exception)
            self.assertIn('|mAOD|', app.session_state['workbench_reference'])
            picker = next(x for x in app.selectbox if x.label == 'Measurement reference')
            picker.set_value('E70139|m|datum:old').run()
        self.assertFalse(app.exception)
        points = next(layer.data for layer in decks[-1].layers if layer.id == 'monitoring-points')
        point = next(row for row in points if row['entity_id'] == 'water:E70139')
        self.assertEqual(point['state'], 'Stale')
        self.assertEqual(point['datum_uri'], 'datum:old')

    def test_layer_choices_survive_switching_example_context(self):
        app = self.app()
        next(x for x in app.checkbox if x.label == 'Traffic counters').uncheck().run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Example network').run()
        next(x for x in app.radio if x.label == 'Data view').set_value('Connected observations').run()
        self.assertFalse(app.exception)
        self.assertFalse(next(x for x in app.checkbox if x.label == 'Traffic counters').value)

    def test_run_id_can_match_the_empty_selection_label(self):
        package = validate_package(dict(package_template('model_run'), run_id='No run selected'))
        app = self.results_app({'No run selected': package})
        next(x for x in app.selectbox if x.label == 'Current run').set_value('No run selected').run()
        self.assertFalse(app.exception)
        self.assertIn('current_run_id', app.session_state)
        self.assertEqual(app.session_state['current_run_id'], 'No run selected')

    def test_deeply_nested_upload_is_rejected_without_crashing(self):
        with patch('streamlit.file_uploader', return_value=BytesIO(('[' * 20000 + '0' + ']' * 20000).encode())):
            app = AppTest.from_string("from workbench_views import _import_package\n_import_package('data')", default_timeout=30).run()
            next(x for x in app.button if x.label == 'Validate & add to this session').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Package rejected' in x.value for x in app.error))

    def test_imported_metadata_is_not_rendered_as_markdown_images(self):
        injected = 'Injected ![remote](https://invalid.example/metadata)'
        package = validate_package(dict(package_template('model_run'), model_name=injected, run_id=injected, scenario_id=injected))
        app = self.results_app({injected: package}, injected)
        self.assertFalse(app.exception)
        self.assertFalse(any('![remote]' in str(x.value) for x in list(app.markdown) + list(app.caption)))

    def test_large_partner_values_remain_inspectable_without_chart_overflow(self):
        first = package_template('model_run')
        first['outputs'][0]['value'] = 10 ** 400
        second = package_template('model_run')
        second['run_id'] = 'large-b'
        second['outputs'][0]['value'] = 10 ** 400 + 1
        app = self.results_app({first['run_id']: validate_package(first), second['run_id']: validate_package(second)}, first['run_id'])
        self.assertFalse(app.exception)
        self.assertTrue(any(str(10 ** 400) in [str(v) for v in x.value.to_numpy().flat] for x in app.dataframe))
        self.assertTrue(any('chart' in x.value.lower() and 'range' in x.value.lower() for x in app.info))

    def test_comparison_errors_render_provider_ids_as_plain_text(self):
        first = package_template('model_run')
        injected = 'Injected ![remote](https://invalid.example/metadata)'
        first['run_id'] = injected
        first['outputs'].append(dict(first['outputs'][0]))
        second = package_template('model_run')
        app = self.results_app({injected: validate_package(first), second['run_id']: validate_package(second)})
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertFalse(any('![remote]' in str(x.value) for x in app.warning))


if __name__ == '__main__':
    unittest.main()
