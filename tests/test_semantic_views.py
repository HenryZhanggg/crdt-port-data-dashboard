import json
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from semantic_service import SemanticDemo


class SemanticViewTests(unittest.TestCase):
    def app(self, **state):
        st.cache_data.clear()
        fetch = patch('api_connectors.fetch_raw_data_bundle')
        self.fetch = fetch.start()
        self.addCleanup(fetch.stop)
        daily = patch('daily_service.load_daily_snapshot')
        self.daily = daily.start()
        self.addCleanup(daily.stop)
        app = AppTest.from_string('from semantic_views import render_semantic_demo\nrender_semantic_demo()', default_timeout=30)
        for key, value in state.items():
            app.session_state[key] = value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_example_uses_fixed_sample_day_and_no_live_feeds(self):
        app = self.app()
        self.assertTrue(any(x.label == 'Object type' for x in app.selectbox))
        self.assertTrue(any(x.label == 'Relationship' for x in app.selectbox))
        text = ' '.join(str(x.value) for x in list(app.markdown) + list(app.caption))
        self.assertIn('14 NOV 2026', text.upper())
        self.assertIn('ILLUSTRATIVE', text.upper())
        self.assertIn('DRAFT ONTOLOGY', text.upper())
        self.assertFalse(app.date_input)
        self.fetch.assert_not_called()
        self.daily.assert_not_called()
        self.assertFalse(app.session_state.filtered_state.get('partner_runs', {}))

    def test_one_map_and_four_object_tabs_replace_duplicate_modes_and_panels(self):
        app = self.app()
        self.assertEqual([tab.label for tab in app.tabs], ['Readings', 'Connections', 'Results', 'Sources'])
        self.assertFalse(any(x.label in {'Network data', 'Content mode', 'Spatial view'} for x in app.radio))
        self.assertFalse(any(x.label in {'Run model', 'View illustrative results'} for x in app.button))
        self.assertEqual(len(app.get('deck_gl_json_chart')), 1)

    def test_type_selection_changes_object_and_reading_products(self):
        app = self.app()
        next(x for x in app.selectbox if x.label == 'Object type').set_value('demo:MonitoringStation').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:gauge_a')
        gauge_titles = {product['title'] for product in SemanticDemo().products('demo:gauge_a', 'observations')}
        self.assertTrue(any(title in x.value for title in gauge_titles for x in app.markdown))
        next(x for x in app.selectbox if x.label == 'Object type').set_value('demo:Terminal').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:terminal_a')
        state_titles = {product['title'] for product in SemanticDemo().products('demo:terminal_a', 'state')}
        self.assertTrue(any(title in x.value for title in state_titles for x in app.markdown))

    def test_relation_filter_changes_declared_links(self):
        app = self.app()
        next(x for x in app.selectbox if x.label == 'Relationship').set_value('demo:dependsOn').run()
        self.assertFalse(app.exception)
        text = ' '.join(str(x.value) for x in app.caption)
        self.assertIn('1 declared', text)
        self.assertTrue(any(x.key == 'semantic_related_demo:power_a' for x in app.button))

    def test_related_jump_uses_same_selection_context(self):
        app = self.app()
        next(x for x in app.selectbox if x.label == 'Relationship').set_value('demo:dependsOn').run()
        next(x for x in app.button if x.key == 'semantic_related_demo:power_a').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:power_a')
        self.assertTrue(any('UtilityFacility' in str(x.value) for x in app.markdown))

    def test_scenario_selector_lives_in_results_and_changes_synthetic_outputs(self):
        app = self.app()
        self.assertIn('Results', [tab.label for tab in app.tabs])
        results = next(tab for tab in app.tabs if tab.label == 'Results')
        self.assertTrue(any(x.label == 'Scenario' and not x.disabled for x in results.selectbox))
        next(x for x in app.selectbox if x.label == 'Scenario').set_value('demo:service').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_scenario'], 'demo:service')
        expected = SemanticDemo().products('demo:terminal_a', 'scenario', scenario_id='demo:service')
        results = next(tab for tab in app.tabs if tab.label == 'Results')
        self.assertTrue(any(expected[0]['title'] in x.value for x in results.markdown))
        self.assertTrue(any('synthetic' in str(x.value).casefold() or 'illustrative' in str(x.value).casefold()
                            for x in results.caption))

    def test_demo_source_entities_do_not_replace_live_selection(self):
        app = self.app(workbench_entity_id='water:E70139')
        next(x for x in app.selectbox if x.label == 'Object type').set_value('demo:Road').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'], 'water:E70139')

    def test_native_map_pick_updates_shared_object(self):
        event = {'selection': {'objects': {'semantic_objects': [{'entity_id': 'demo:gauge_a'}]}}}
        with patch('streamlit.pydeck_chart', return_value=event):
            app = self.app()
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:gauge_a')
        self.assertTrue(any('demo:gauge_a' in str(x.value) for x in app.caption))

    def test_native_map_pick_clears_an_incompatible_type_and_search_filter(self):
        event = {'selection': {'objects': {'semantic_labels': [{'entity_id': 'demo:power_a'}]}}}
        with patch('streamlit.pydeck_chart', return_value=event):
            app = self.app(semantic_type='demo:Terminal', semantic_search='terminal')
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:power_a')
        self.assertEqual(app.session_state['semantic_type'], 'All')
        self.assertEqual(app.session_state['semantic_search'], '')

    def test_type_change_clears_a_previous_native_selection(self):
        event = {'selection': {'objects': {'semantic_objects': [{'entity_id': 'demo:terminal_a'}]}}}
        def chart(deck, **kwargs):
            return event if kwargs['key'] == 'semantic_map_0' else {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=chart):
            app = self.app()
            next(x for x in app.selectbox if x.label == 'Object type').set_value('demo:Road').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:road_a')
        self.assertEqual(app.session_state['semantic_type'], 'demo:Road')

    def test_search_selects_a_matching_asset_and_handles_no_match(self):
        app = self.app()
        next(x for x in app.text_input if x.label == 'Search assets').set_value('gauge').run()
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:gauge_a')
        next(x for x in app.text_input if x.label == 'Search assets').set_value('no-such-asset').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No assets match' in x.value for x in app.info))

    def test_manual_choice_clears_a_retained_native_pick(self):
        event = {'selection': {'objects': {'semantic_objects': [{'entity_id': 'demo:terminal_a'}]}}}
        def chart(deck, **kwargs):
            return event if kwargs['key'] == 'semantic_map_0' else {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=chart):
            app = self.app()
            next(x for x in app.button if x.key == 'semantic_object_demo:gauge_a').click().run()
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:gauge_a')

    def test_search_change_clears_a_retained_native_pick(self):
        event = {'selection': {'objects': {'semantic_objects': [{'entity_id': 'demo:terminal_a'}]}}}
        def chart(deck, **kwargs):
            return event if kwargs['key'] == 'semantic_map_0' else {'selection': {'objects': {}}}
        with patch('streamlit.pydeck_chart', side_effect=chart):
            app = self.app()
            next(x for x in app.text_input if x.label == 'Search assets').set_value('road').run()
        self.assertEqual(app.session_state['semantic_entity_id'], 'demo:road_a')

    def test_connections_expose_canonical_direction_and_local_evidence_provider(self):
        app = self.app(semantic_relation='demo:dependsOn')
        connections = next(tab for tab in app.tabs if tab.label == 'Connections')
        text = ' '.join(str(x.value) for x in connections.caption)
        self.assertIn('demo:terminal_a → demo:power_a', text)
        self.assertIn('Illustrative dependency assertion', text)
        self.assertIn('2026-11-14', text)

    def test_example_map_retains_all_five_assets_and_geographic_arrows(self):
        with patch('streamlit.pydeck_chart', return_value={'selection': {}}) as chart:
            self.app(semantic_relation='demo:dependsOn')
        deck = json.loads(chart.call_args.args[0].to_json())
        layers = {layer['id']: layer for layer in deck['layers']}
        service = SemanticDemo()
        self.assertEqual({row['entity_id'] for row in layers['semantic_objects']['data']},
                         {row['entity_id'] for row in service.entities()})
        links = layers['semantic_links']['data']
        self.assertEqual([(edge['source_id'], edge['target_id']) for edge in links],
                         [('demo:terminal_a', 'demo:power_a')])
        self.assertEqual(len(layers['semantic_arrows']['data']), 1)
        source = service.entity('demo:terminal_a')
        target = service.entity('demo:power_a')
        self.assertEqual(links[0]['source'], [source['lon'], source['lat']])
        self.assertEqual(links[0]['target'], [target['lon'], target['lat']])

    def test_gauge_readings_keep_declared_datum_and_gap_values(self):
        with patch('streamlit.plotly_chart', return_value={'selection': {}}) as chart:
            app = self.app(semantic_type='demo:MonitoringStation')
        expected = SemanticDemo().products('demo:gauge_a', 'observations')[0]
        expected_values = [row[expected['metrics'][0]['key']] for row in expected['rows']]
        values = list(chart.call_args_list[0].args[0].data[0].y)
        self.assertEqual([None if pd.isna(value) else value for value in values], expected_values)
        reference = expected['metrics'][0].get('datum')
        if reference:
            self.assertTrue(any(reference in x.value for x in app.caption))


if __name__ == '__main__':
    unittest.main()
