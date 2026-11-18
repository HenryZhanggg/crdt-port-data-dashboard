import io
import json
import unittest
import zipfile
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from api_connectors import empty_bundle
from tabular_integration import read_csv_upload, map_tabular_observations
from test_integration_views import integration_fixture


class JointIntegrationViewTests(unittest.TestCase):
    def upload(self):
        now = pd.Timestamp.now(tz='UTC').floor('s')
        text = 'id,value,time\nCSV-gauge,1.3,' + (now-pd.Timedelta(minutes=10)).isoformat() + '\n'
        frame = read_csv_upload(text.encode())
        records = map_tabular_observations(frame,
            {'entity_id': 'id', 'value': 'value', 'event_time': 'time'},
            {'metric': 'level', 'unit': 'mAOD', 'kind': 'water_level',
             'datum_uri': 'http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD',
             'qualifier': 'Tidal Level'}, now.isoformat())
        return records, {'collected_at': now.isoformat(), 'requested_sources': ['csv_upload'],
            'collection_status': [{'source_id': records.iloc[0]['source_id'], 'status': 'mapped_upload', 'records': 1}],
            'collection_period': None, 'observation_context': None,
            'traffic_timezone_assumption': None, 'filename': 'observations.csv'}

    def app(self, bundle=None, **state):
        app = AppTest.from_string('''import streamlit as st
from integration_views import render_integration_workspace
def load(start,end,sources):
    st.session_state['requests']=st.session_state.get('requests',0)+1
    return st.session_state['bundle']
render_integration_workspace(load, st.session_state.get('views', {'weather','transport','raw_data'}))
''', default_timeout=30)
        app.session_state['bundle'] = integration_fixture() if bundle is None else bundle
        for key, value in state.items():
            app.session_state[key] = value
        return app

    def collect(self, app):
        next(x for x in app.button if x.label == 'Load selected records').click().run()
        self.assertFalse(app.exception)

    def test_combined_intake_uses_both_sources_without_implicit_requests(self):
        upload = self.upload()
        with patch('integration_views.render_csv_mapping', return_value=upload):
            app = self.app().run()
            self.assertIn('Combine API + CSV', app.radio(key='integration_input_kind').options)
            app.radio(key='integration_input_kind').set_value('Combine API + CSV').run()
            self.assertNotIn('requests', app.session_state)
            self.collect(app)
        sources = next(x.value for x in app.dataframe if 'source_id' in x.value and 'event_time' in x.value)
        self.assertEqual(set(sources['source_id']), {'HS004', upload[0].iloc[0]['source_id']})
        self.assertEqual(app.session_state['requests'], 1)
        self.assertTrue(any('common' in str(x.value).lower() for x in app.caption))

    def test_joint_export_retains_mapping_and_partial_api_failure(self):
        upload = self.upload()
        bundle = empty_bundle()
        bundle['status'] = pd.DataFrame([{'connector_id': 'ea_liverpool_tide_water_level_api',
            'status': 'api_error', 'records': 0, 'access_note': 'Upstream unavailable'}])
        with patch('integration_views.render_csv_mapping', return_value=upload):
            app = self.app(bundle, integration_input_kind='Combine API + CSV').run()
            with patch('streamlit.download_button') as download, patch('streamlit.delta_generator.DeltaGenerator.download_button', download):
                self.collect(app)
        exported = next((x for x in download.call_args_list if x.args[0] == 'Download integration report ZIP'), None)
        self.assertIsNotNone(exported, 'Combined intake must export a joint report despite one failed API')
        with zipfile.ZipFile(io.BytesIO(exported.args[1])) as archive:
            rules = json.loads(archive.read('rules.json'))
            self.assertEqual(rules['requested_sources'], ['water_level', 'csv_upload'])
            self.assertEqual(rules['collection_status'][0]['status'], 'api_error')
            self.assertIsNone(rules['collection_period'])
            self.assertIsNone(rules['observation_context'])
            self.assertIn('start',rules['input_collection']['api_request_period'])
            self.assertIn('api_observation_context',rules['input_collection'])
            self.assertIn('bindings', rules['joint_product'])
            self.assertIn('linkage', rules['joint_product'])
            self.assertEqual(len(rules['input_collection']['collections']), 2)
        self.assertFalse(app.exception)

    def test_linkage_editor_retains_edits_after_two_runs(self):
        app = self.app().run()
        self.collect(app)
        editor = next((x for x in app.dataframe if 'common_entity_id' in x.value), None)
        self.assertIsNotNone(editor, 'Common identity and concept declarations must be editable')
        state = app._tree.get_widget_states()
        state.widgets.add(id=editor.proto.id, string_value=json.dumps({'edited_rows': {
            '0': {'common_entity_id': 'port:station-1', 'common_concept': 'https://example.org/level', 'confirmed': True}},
            'added_rows': [], 'deleted_rows': []}))
        app._run(state)
        self.assertFalse(app.exception)
        app.number_input(key='integration_freshness').set_value(65).run()
        editor = next(x for x in app.dataframe if 'common_entity_id' in x.value)
        self.assertEqual(editor.value.iloc[0]['common_entity_id'], 'port:station-1')
        self.assertTrue(editor.value.iloc[0]['confirmed'])

    def test_restricted_view_never_renders_combined_inputs_or_retained_records(self):
        app = self.app(views={'weather','data_status'}, integration_upload_records=self.upload()[0]).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        self.assertFalse(app.dataframe)
        self.assertNotIn('requests', app.session_state)
