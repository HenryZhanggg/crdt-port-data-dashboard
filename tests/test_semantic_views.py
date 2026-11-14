import unittest
from datetime import date
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from test_dashboard_views import observation_fixture


class SemanticViewTests(unittest.TestCase):
    def app(self, **state):
        st.cache_data.clear()
        fetch=patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture())
        self.fetch=fetch.start()
        self.addCleanup(fetch.stop)
        app=AppTest.from_file('app.py', default_timeout=30)
        app.session_state['dashboard_authorised']=True
        for key,value in state.items():
            app.session_state[key]=value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_default_home_is_semantic_demo_without_fetching_live_feeds(self):
        app=self.app()
        self.assertTrue(any('Ontology-guided workspace' in x.value for x in app.subheader))
        self.assertTrue(any(x.label=='Object type' for x in app.selectbox))
        self.assertTrue(any(x.label=='Relationship' for x in app.selectbox))
        self.fetch.assert_not_called()
        self.assertFalse(app.session_state.filtered_state.get('partner_runs',{}))

    def test_type_selection_changes_object_and_view_profile(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Object type').set_value('demo:MonitoringStation').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:gauge_a')
        self.assertTrue(any(x.label=='Water level' for x in app.tabs))
        next(x for x in app.selectbox if x.label=='Object type').set_value('demo:Terminal').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:terminal_a')
        self.assertTrue(any(x.label=='Terminal state' for x in app.tabs))

    def test_relation_filter_changes_declared_links(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Relationship').set_value('demo:dependsOn').run()
        self.assertFalse(app.exception)
        text=' '.join(str(x.value) for x in app.caption)
        self.assertIn('1 declared',text)
        self.assertTrue(any(x.key=='semantic_related_demo:power_a' for x in app.button))

    def test_related_jump_uses_same_selection_context(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Relationship').set_value('demo:dependsOn').run()
        next(x for x in app.button if x.key=='semantic_related_demo:power_a').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:power_a')
        self.assertTrue(any('UtilityFacility' in str(x.value) for x in app.code))

    def test_scenario_and_graph_selection_are_available(self):
        app=self.app()
        next(x for x in app.radio if x.label=='Content mode').set_value('Scenario results').run()
        next(x for x in app.selectbox if x.label=='Scenario').set_value('demo:service').run()
        next(x for x in app.radio if x.label=='Spatial view').set_value('Relations').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_scenario'],'demo:service')
        self.assertTrue(app.get('plotly_chart'))
        self.assertTrue(any(x.label=='Run model' and x.disabled for x in app.button))

    def test_live_monitoring_remains_accessible(self):
        app=self.app()
        next(x for x in app.button if x.label=='Monitor').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any(x.label=='Inspect an object' for x in app.selectbox))
        self.fetch.assert_called()

    def test_previous_demo_navigation_is_removed_and_stale_state_recovers(self):
        app=self.app(workspace_section='WP Delivery', **{'workspace_view_WP Delivery':'Integration Demo'})
        self.assertFalse(any(x.label=='Integration demo' for x in app.button))
        self.assertNotIn('Integration Demo',next(x for x in app.radio if x.label=='View').options)

    def test_demo_source_entities_do_not_replace_live_selection(self):
        app=self.app(workbench_entity_id='water:E70139')
        next(x for x in app.selectbox if x.label=='Object type').set_value('demo:Road').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'],'water:E70139')

    def test_native_map_pick_updates_shared_object(self):
        event={'selection':{'objects':{'semantic_objects':[{'entity_id':'demo:gauge_a'}]}}}
        with patch('streamlit.pydeck_chart', return_value=event):
            app=self.app()
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:gauge_a')
        self.assertTrue(any(x.label=='Water level' for x in app.tabs))

    def test_native_graph_pick_clears_an_incompatible_type_filter(self):
        event={'selection':{'points':[{'customdata':['demo:power_a']}]}}
        with patch('streamlit.plotly_chart', return_value=event):
            app=self.app(semantic_spatial_view='Relations',semantic_type='demo:Terminal')
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:power_a')
        self.assertEqual(app.session_state['semantic_type'],'All')

    def test_graph_picks_the_closest_node_in_both_dimensions(self):
        with patch('streamlit.plotly_chart', return_value={'selection':{}}) as chart:
            self.app(semantic_spatial_view='Relations')
        self.assertEqual(chart.call_args_list[0].args[0].layout.hovermode, 'closest')

    def test_type_change_clears_a_previous_native_selection(self):
        event={'selection':{'objects':{'semantic_objects':[{'entity_id':'demo:terminal_a'}]}}}
        def selected_only_on_original_chart(deck, **kwargs):
            return event if kwargs['key']=='semantic_map_0' else {'selection':{'objects':{}}}
        with patch('streamlit.pydeck_chart', side_effect=selected_only_on_original_chart):
            app=self.app()
            next(x for x in app.selectbox if x.label=='Object type').set_value('demo:Road').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['semantic_entity_id'],'demo:road_a')
        self.assertEqual(app.session_state['semantic_type'],'demo:Road')

    def test_period_outside_sample_coverage_shows_no_matching_products(self):
        app=self.app()
        next(x for x in app.date_input if x.label=='Demo period').set_value((date(2026,11,10),date(2026,11,11))).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No sample product matches' in x.value for x in app.info))


if __name__=='__main__':
    unittest.main()
