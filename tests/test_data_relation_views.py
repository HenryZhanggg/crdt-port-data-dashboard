import json
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from test_dashboard_views import observation_fixture
from workbench_data import build_entities


def water_context():
    frame=observation_fixture()['water_levels']
    return {'source':'water_level','source_id':'HS004','entity_id':'water:E70139',
        'station_reference':'E70139','unit':'mAOD',
        'datum_uri':'http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD',
        'start':str(frame['date_time'].min().date()),'end':str(frame['date_time'].max().date())}


class DataRelationViewTests(unittest.TestCase):
    def test_graph_tooltip_does_not_embed_an_unbounded_reading_uri_register(self):
        from data_relation_views import _relation_dot
        graph={'nodes':[{'id':'records:one','label':'672 raw records','kind':'Records',
                         'evidence':'Source-derived','detail':{'reading_sources':'https://example.org/reading/'*3000}}],
               'edges':[]}
        dot=_relation_dot(graph)
        self.assertLess(len(dot),2000)

    def app(self, context=None, bundle=None, **state):
        bundle=observation_fixture() if bundle is None else bundle
        app=AppTest.from_string("""import streamlit as st
from data_relation_views import render_data_relations
render_data_relations(st.session_state['test_bundle'],st.session_state['test_context'],st.session_state['test_entities'])
""",default_timeout=30)
        app.session_state['test_bundle']=bundle
        app.session_state['test_context']=context or water_context()
        app.session_state['test_entities']=build_entities(bundle)
        for key,value in state.items():app.session_state[key]=value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_real_connections_show_without_a_dependency_package_and_export_exact_reference(self):
        from unittest.mock import patch
        with patch('streamlit.download_button') as download:
            app=self.app()
        self.assertTrue(app.get('graphviz_chart'))
        self.assertEqual(next(x for x in app.metric if x.label=='Returned records').value,'12')
        call=next(c for c in download.call_args_list if c.args[0]=='Download connection evidence')
        evidence=json.loads(call.args[1])
        self.assertEqual(evidence['metadata']['selected_object'],'water:E70139')
        ids={n['id'] for n in evidence['nodes']}
        self.assertIn('water:E70139',ids)
        self.assertNotIn('water:E70124',ids)

    def test_traffic_mapping_and_time_limits_remain_visible(self):
        context=water_context()
        context.update(source='webtris',source_id='HS007',entity_id='traffic:6806',site_id='6806')
        app=self.app(context)
        visible='\n'.join(str(x.value) for x in list(app.caption)+list(app.info))
        self.assertIn('Mapping unverified',visible)
        self.assertIn('timezone unverified',visible.lower())

    def test_nearby_object_action_releases_incoming_context(self):
        app=self.app(monitor_handoff=water_context())
        picker=next(x for x in app.selectbox if x.label=='Nearby object')
        picker.set_value('traffic:6806').run()
        next(x for x in app.button if x.label=='Inspect nearby object').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['workbench_entity_id'],'traffic:6806')
        self.assertNotIn('monitor_handoff',app.session_state)
        self.assertEqual(app.session_state['workbench_map_revision'],1)

    def test_no_records_does_not_draw_an_observation_chain(self):
        bundle=observation_fixture()
        bundle['water_levels']=bundle['water_levels'].iloc[:0]
        app=self.app(bundle=bundle)
        self.assertFalse(app.get('graphviz_chart'))
        self.assertTrue(any('No returned records' in x.value for x in app.info))


if __name__=='__main__':unittest.main()
