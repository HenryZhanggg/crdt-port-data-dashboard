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
    def app(self, default_tab="Sources", **state):
        app=AppTest.from_string("""import streamlit as st
import pandas as pd
from data_views import render_data_workspace
def load(start,end,sources):
    st.session_state['requested_sources']=list(sources)
    return st.session_state['test_bundle']
catalog=pd.read_csv('data/high_score_dataset_catalog.csv').fillna('')
render_data_workspace(catalog,load,st.session_state.get('allowed_views',{'weather','transport','raw_data','data_status','dataset_catalog','gis'}))
""",default_timeout=30)
        app.session_state['test_bundle']=observation_fixture()
        if default_tab is not None:
            app.session_state['data_workspace_tab']=default_tab
        for key,value in state.items():
            app.session_state[key]=value
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_default_workspace_opens_integration_without_collecting(self):
        app=self.app(default_tab=None)
        self.assertEqual(app.session_state['data_workspace_tab'],'Integration')
        self.assertNotIn('requested_sources',app.session_state)
        self.assertTrue(any(x.label=='Load selected records' for x in app.button))
        self.assertEqual([x.label for x in app.tabs[:3]],['Integration','Sources','Quality'])

    def handoff(self, tab='Sources', **changes):
        from workspace_links import open_data_context
        dates=observation_fixture()['water_levels']['date_time']
        context={'source':'water_level','source_id':'HS004','entity_id':'water:E70124',
            'station_reference':'E70124','unit':'m','datum_uri':'https://example.org/test/local-datum',
            'start':dates.min().date().isoformat(),'end':dates.max().date().isoformat()}
        context.update(changes)
        state={}
        with patch('workspace_links.st.session_state',state):
            open_data_context(context,tab)
        return state

    def test_source_handoff_filters_csv_to_exact_reference_without_mutating_cache(self):
        with patch('streamlit.download_button') as download:
            app=self.app(**self.handoff())
        self.assertEqual(app.session_state['requested_sources'],['water_level'])
        exported=next(call for call in download.call_args_list if call.args[0]=='Download dataset CSV')
        rows=pd.read_csv(io.BytesIO(exported.args[1]))
        self.assertEqual(set(rows['station_reference']),{'E70124'})
        self.assertEqual(set(rows['datum_uri']),{'https://example.org/test/local-datum'})
        self.assertEqual(len(app.session_state['test_bundle']['water_levels']),24)
        self.assertTrue(any('Observation context' in x.value for x in app.caption))
        self.assertTrue(any(x.label=='Clear observation context' for x in app.button))

    def test_quality_handoff_filters_table_report_and_graph_to_exact_reference(self):
        with patch('streamlit.download_button') as download, patch('streamlit.delta_generator.DeltaGenerator.download_button', download):
            app=self.app(**self.handoff('Quality'))
        self.assertEqual(app.session_state['requested_sources'],['water_level'])
        quality=next(call for call in download.call_args_list if call.args[0]=='Download quality CSV')
        rows=pd.read_csv(io.BytesIO(quality.args[1]))
        self.assertEqual(rows['Source'].tolist(),['Water E70124 | m'])
        report=next(call for call in download.call_args_list if call.args[0]=='Export observation report')
        with zipfile.ZipFile(io.BytesIO(report.args[1])) as archive:
            observations=pd.read_csv(io.BytesIO(archive.read('water_observations.csv')))
            self.assertEqual(set(observations['station_reference']),{'E70124'})
            self.assertTrue(pd.read_csv(io.BytesIO(archive.read('traffic_observations.csv'))).empty)
        graph=next(call for call in download.call_args_list if call.args[0]=='Download observation graph (Turtle)')
        self.assertIn('E70124',graph.args[1])
        self.assertNotIn('E70139',graph.args[1])

    def test_missing_context_reference_has_clear_action_and_no_alternative_export(self):
        app=self.app(**self.handoff(datum_uri='datum:not-returned'))
        self.assertTrue(any('requested measurement reference' in x.value.lower() for x in app.info))
        self.assertFalse(any(x.label=='Download dataset CSV' for x in app.get('download_button')))
        next(x for x in app.button if x.label=='Clear observation context').click().run()
        self.assertFalse(app.exception)
        self.assertNotIn('data_handoff',app.session_state)
        self.assertTrue(any(x.label=='Download dataset CSV' for x in app.get('download_button')))

    def test_empty_response_keeps_requested_quality_context_without_generic_exports(self):
        from api_connectors import empty_bundle
        app=self.app(test_bundle=empty_bundle(),**self.handoff('Quality'))
        self.assertTrue(any('requested measurement reference' in x.value.lower() for x in app.info))
        self.assertEqual(app.session_state['data_handoff']['station_reference'],'E70124')
        self.assertFalse(any(x.label in {'Download quality CSV','Export observation report'} for x in app.get('download_button')))

    def test_context_permissions_prevent_forbidden_family_request(self):
        app=self.app(allowed_views={'transport','raw_data','dataset_catalog'},**self.handoff())
        self.assertNotIn('requested_sources',app.session_state)
        self.assertTrue(any('outside this partner view' in x.value for x in app.info))

    def test_quality_handoff_preserves_existing_quality_permission_without_raw_preview(self):
        app=self.app(allowed_views={'weather','data_status'},**self.handoff('Quality'))
        self.assertEqual(app.session_state['requested_sources'],['water_level'])
        self.assertTrue(any(x.label=='Download quality CSV' for x in app.get('download_button')))

    def test_user_source_table_and_quality_scope_changes_clear_context(self):
        for tab,label,value in [('Sources','Data source','HS007'),
                                ('Sources','Dataset','ea_stations'),
                                ('Quality','Check data','Road traffic')]:
            with self.subTest(label=label):
                app=self.app(**self.handoff(tab))
                next(x for x in app.selectbox if x.label==label).set_value(value).run()
                self.assertFalse(app.exception)
                self.assertNotIn('data_handoff',app.session_state)

    def test_traffic_handoff_keeps_counter_and_source_timezone_in_report(self):
        dates=observation_fixture()['webtris_daily']['timestamp']
        state=self.handoff('Quality',source='webtris',source_id='HS007',entity_id='traffic:6806',site_id='6806',
                           start=dates.min().date().isoformat(),end=dates.max().date().isoformat())
        bundle=observation_fixture()
        bundle['webtris_daily']=pd.concat([bundle['webtris_daily'],bundle['webtris_daily'].assign(site_id='6807')])
        with patch('streamlit.download_button') as download, patch('streamlit.delta_generator.DeltaGenerator.download_button', download):
            app=self.app(test_bundle=bundle,**state)
        self.assertEqual(app.session_state['requested_sources'],['webtris'])
        report=next(call for call in download.call_args_list if call.args[0]=='Export observation report')
        with zipfile.ZipFile(io.BytesIO(report.args[1])) as archive:
            traffic=pd.read_csv(io.BytesIO(archive.read('traffic_observations.csv')))
            self.assertEqual(set(traffic['site_id']),{6806})
            metadata=json.loads(archive.read('metadata.json'))
            self.assertIn('timezone unverified',metadata['traffic_time_basis'])

    def test_catalogue_does_not_fetch_sources_until_a_source_is_selected(self):
        app=self.app()
        self.assertNotIn('requested_sources',app.session_state.filtered_state)
        self.assertFalse(app.date_input)
        self.assertTrue(any(x.label=='Data source' for x in app.selectbox))

    def test_report_role_filter_changes_catalogue_without_requesting_sources(self):
        app=self.app()
        next(x for x in app.selectbox if x.label=='Data role').set_value('Updated observations').run()
        self.assertFalse(app.exception)
        self.assertNotIn('requested_sources',app.session_state)
        register=next(x.value for x in app.dataframe if 'Report evidence' in x.value)
        self.assertEqual(register['ID'].tolist(),['HS004'])
        self.assertEqual(register.iloc[0]['Report evidence'],'Assessed in report')

    def test_selected_source_shows_report_findings_without_claiming_runtime_access(self):
        app=self.app(data_source_id='HS007')
        self.assertNotIn('requested_sources',app.session_state)
        self.assertTrue(any('P0940-REP-103 C1' in x.value and '86' in x.value for x in app.caption))
        self.assertTrue(any('one month' in str(x.value).lower() for x in app.caption))

    def test_integration_tab_is_lazy_until_explicit_collection(self):
        app=self.app(data_workspace_tab='Integration')
        self.assertNotIn('requested_sources',app.session_state)
        self.assertTrue(any(x.label=='Load selected records' for x in app.button))
        self.assertFalse(any(x.label=='Data source' for x in app.selectbox))

    def test_traffic_catalogue_explains_publication_delay_without_requesting_records(self):
        app=self.app(data_source_id='HS007')
        self.assertNotIn('requested_sources',app.session_state)
        self.assertTrue(any('one month after collection' in x.value for x in app.caption))

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
        self.assertEqual(app.session_state['data_workspace_tab'],'Integration')
        self.assertTrue(any(x.label=='Partner products and dependencies' for x in app.expander))
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
