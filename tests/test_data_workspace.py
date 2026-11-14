import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import pandas as pd
from streamlit.testing.v1 import AppTest

from test_dashboard_views import observation_fixture


class DataWorkspaceTests(unittest.TestCase):
    def app(self, **state):
        app=AppTest.from_string("""import streamlit as st
import pandas as pd
from data_views import render_data_workspace
def load(start,end,sources):
    st.session_state['requested_sources']=list(sources)
    return st.session_state['test_bundle']
catalog=pd.read_csv('data/high_score_dataset_catalog.csv').fillna('')
render_data_workspace(catalog,load,{'weather','transport','raw_data','data_status','dataset_catalog','gis'})
""",default_timeout=30)
        app.session_state['test_bundle']=observation_fixture()
        for key,value in state.items():
            app.session_state[key]=value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_catalogue_does_not_fetch_sources_until_a_source_is_selected(self):
        app=self.app()
        self.assertNotIn('requested_sources',app.session_state.filtered_state)
        self.assertFalse(app.date_input)
        self.assertTrue(any(x.label=='Data source' for x in app.selectbox))

    def test_selected_port_source_does_not_request_monitoring_sources(self):
        app=self.app(data_source_id='HS001',data_browse_HS001=True)
        self.assertEqual(app.session_state['requested_sources'],['dft'])
        self.assertFalse(app.date_input)
        self.assertTrue(any(x.label=='Dataset' for x in app.selectbox))

    def test_deferred_source_keeps_metadata_without_calling_unavailable_connector(self):
        app=self.app(data_source_id='HS011')
        self.assertNotIn('requested_sources',app.session_state.filtered_state)
        self.assertTrue(any('partner' in str(x.value).lower() for x in app.caption))

    def test_water_source_keeps_reference_metadata_and_raw_csv(self):
        app=self.app(data_source_id='HS004',data_browse_HS004=True)
        self.assertEqual(set(app.session_state['requested_sources']),{'water_level','ea'})
        self.assertTrue(app.date_input)
        self.assertTrue(any(x.label=='Download dataset CSV' for x in app.get('download_button')))
        self.assertTrue(any('datum' in str(x.value).lower() for x in app.caption))

    def test_partner_intake_has_no_observation_dates_or_feed_calls(self):
        app=self.app(data_workspace_tab='Partner packages',data_source_id='HS004')
        self.assertNotIn('requested_sources',app.session_state.filtered_state)
        self.assertFalse(app.date_input)
        self.assertEqual(len(app.get('file_uploader')),1)

    def test_connected_catalogue_metadata_is_accessible_without_fetching_records(self):
        app=self.app(data_source_id='HS009')
        self.assertNotIn('requested_sources',app.session_state.filtered_state)
        self.assertFalse(app.date_input)
        self.assertTrue(any(x.label=='Catalogue metadata' for x in app.expander))
        self.assertTrue(app.get('json'))

    def test_quality_preserves_detailed_validation_and_report_exports(self):
        app=self.app(data_workspace_tab='Quality')
        self.assertEqual(set(app.session_state['requested_sources']),{'water_level','webtris'})
        labels={x.label for x in app.get('download_button')}
        self.assertIn('Export observation report',labels)
        self.assertIn('Download quality CSV',labels)

    def test_water_quality_does_not_claim_traffic_was_checked(self):
        app=self.app(data_workspace_tab='Quality',data_quality_scope='Water levels')
        self.assertEqual(app.session_state['requested_sources'],['water_level'])
        for table in app.dataframe:
            if 'Source' in table.value:
                self.assertFalse(table.value['Source'].astype(str).str.contains('Traffic|A5036|demonstration').any())

    def test_source_preview_retains_shipping_and_transport_products(self):
        from data_views import SOURCE_PRODUCTS
        frames={key for value in SOURCE_PRODUCTS.values() for key in value['tables']}
        self.assertTrue({'port_traffic','ship_arrivals','weekly_shipping','naptan',
                         'ea_stations','ea_readings','water_levels','webtris_sites','webtris_daily'}<=frames)

    def test_archives_preserve_scientific_evidence_and_draft_project_records(self):
        from project_archives import project_archive,research_archive
        with zipfile.ZipFile(io.BytesIO(project_archive())) as archive:
            names=set(archive.namelist())
            self.assertIn('wp_modules.json',names)
            self.assertEqual(len(json.loads(archive.read('demonstrator_tasks.json'))),4)
            self.assertIn('DRAFT',archive.read('governance_handover.json').decode())
            self.assertFalse(any('secret' in name.lower() for name in names))
        with zipfile.ZipFile(io.BytesIO(research_archive())) as archive:
            self.assertEqual(archive.read('research_signature_summary.csv'),Path('data/research_signature_summary.csv').read_bytes())
            self.assertIn('research_signature_folds.csv',archive.namelist())
            self.assertIn('research_provenance.json',archive.namelist())


if __name__=='__main__':
    unittest.main()
