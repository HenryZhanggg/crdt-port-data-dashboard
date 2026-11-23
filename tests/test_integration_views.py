import io
import json
import unittest
import zipfile
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from api_connectors import empty_bundle, status_row


def integration_fixture():
    bundle = empty_bundle()
    now = pd.Timestamp.now(tz='UTC').floor('s')
    times = pd.date_range(end=now - pd.Timedelta(minutes=10), periods=3, freq='15min')
    bundle['water_levels'] = pd.DataFrame([
        {'station_reference': 'E70139', 'date_time': time, 'value': value,
         'unit': 'mAOD', 'datum_uri': 'http://environment.data.gov.uk/flood-monitoring/def/core/datumAOD',
         'site_key': '53.448,-3.015', 'parameter': 'level', 'qualifier': 'Tidal Level',
         'measure_uri': 'https://example.org/measure/water',
         'api_endpoint': 'https://environment.data.gov.uk/flood-monitoring/data/readings',
         'retrieved_at_utc': now - pd.Timedelta(seconds=1)}
        for time, value in zip(times, [1.1, 1.2, 1.3])
    ])
    bundle['webtris_daily'] = pd.DataFrame({
        'site_id': ['6806'] * 3, 'timestamp': times.tz_localize(None),
        'Total Volume': [20, 30, 40], 'Avg mph': [35, 36, 37]})
    bundle['status'] = pd.DataFrame([
        status_row('ea_liverpool_tide_water_level_api', 'EA water levels', 'Water Level',
                   'api_connected', 3, 'https://environment.data.gov.uk/flood-monitoring', 'Local test fixture'),
        status_row('webtris_daily_a5036_api', 'WebTRIS traffic', 'Traffic',
                   'api_connected', 3, 'https://webtris.highwaysengland.co.uk', 'Local test fixture')])
    return bundle


class IntegrationViewTests(unittest.TestCase):
    def app(self, **state):
        app = AppTest.from_string("""import streamlit as st
from integration_views import render_integration_workspace
def load(start,end,sources):
    st.session_state['test_request_count']=st.session_state.get('test_request_count',0)+1
    st.session_state['test_requested_sources']=list(sources)
    return st.session_state['test_bundle']
render_integration_workspace(load,st.session_state.get('test_views',{'weather','transport','raw_data'}),
    handoff=st.session_state.get('test_handoff'))
""", default_timeout=30)
        app.session_state['test_bundle'] = integration_fixture()
        for key, value in state.items():
            app.session_state[key] = value
        app.run()
        self.assertFalse(app.exception)
        return app

    def load(self, app):
        next(widget for widget in app.button if widget.label == 'Load selected records').click().run()
        self.assertFalse(app.exception)
        return app

    def test_opening_does_not_fetch_and_loading_uses_only_selected_source(self):
        app = self.app()
        self.assertNotIn('test_request_count', app.session_state)
        self.load(app)
        self.assertEqual(app.session_state['test_requested_sources'], ['water_level'])
        self.assertTrue(any(widget.label == 'Download input snapshot CSV' for widget in app.get('download_button')))

    def test_selected_product_previews_and_downloads_share_a_two_column_panel(self):
        app = self.load(self.app())
        columns = app.get('column')
        preview = next((column for column in columns
                        if any(tab.label == 'Integrated records' for tab in column.get('tab'))), None)
        self.assertIsNotNone(preview)
        self.assertTrue(preview.get('dataframe'))
        self.assertTrue(preview.get('plotly_chart'))
        self.assertFalse(preview.get('download_button'))
        exports = next(column for column in columns
                       if any(widget.label == 'Download integration report ZIP'
                              for widget in column.get('download_button')))
        self.assertEqual([widget.label for widget in exports.get('download_button')], [
            'Download integration report ZIP',
            'Download integrated observations CSV',
            'Download input snapshot CSV',
            'Download record audit CSV',
        ])

    def test_rule_changes_reuse_loaded_records_and_expose_stale_state(self):
        app = self.load(self.app())
        next(widget for widget in app.number_input if widget.label == 'Maximum observation age (minutes)').set_value(5).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['test_request_count'], 1)
        outputs = [widget.value for widget in app.dataframe if 'status' in widget.value]
        self.assertTrue(any(frame['status'].eq('Stale').any() for frame in outputs))

    def test_replay_is_labelled_simulated_and_exports_reproducible_package(self):
        app = self.load(self.app())
        with patch('streamlit.download_button') as download, patch('streamlit.delta_generator.DeltaGenerator.download_button', download):
            next(widget for widget in app.radio if widget.label == 'Availability basis').set_value('Replay scenario').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['test_request_count'], 1)
        self.assertTrue(any('simulated' in str(widget.value).lower() for widget in app.warning))
        package = next(call for call in download.call_args_list if call.args[0] == 'Download integration report ZIP')
        with zipfile.ZipFile(io.BytesIO(package.args[1])) as archive:
            self.assertTrue({'observations.csv', 'snapshot.csv', 'audit.csv', 'rules.json'} <= set(archive.namelist()))
            self.assertIn('replay', archive.read('rules.json').decode())

    def test_partial_source_failure_is_retained_in_exported_evidence(self):
        bundle=integration_fixture()
        bundle['webtris_daily']=pd.DataFrame()
        bundle['status'].loc[bundle['status']['connector_id'].eq('webtris_daily_a5036_api'),
                             ['status','records','access_note']]=['api_error',0,'Provider response unavailable']
        app=self.app(test_bundle=bundle,integration_sources=['water_level','webtris'])
        with patch('streamlit.download_button') as download, patch('streamlit.delta_generator.DeltaGenerator.download_button', download):
            self.load(app)
        package=next(call for call in download.call_args_list if call.args[0]=='Download integration report ZIP')
        with zipfile.ZipFile(io.BytesIO(package.args[1])) as archive:
            rules=json.loads(archive.read('rules.json'))
            self.assertEqual(rules['requested_sources'],['water_level','webtris'])
            traffic=next(row for row in rules['collection_status'] if row['connector_id']=='webtris_daily_a5036_api')
            self.assertEqual(traffic['status'],'api_error')
            self.assertEqual(rules['source_ids'],['HS004'])

    def test_empty_collection_can_export_status_without_an_input_snapshot(self):
        bundle=empty_bundle()
        bundle['status']=pd.DataFrame([status_row('ea_liverpool_tide_water_level_api',
            'EA water levels','Water Level','api_error',0,'https://environment.data.gov.uk/flood-monitoring',
            'Upstream unavailable')])
        app=self.app(test_bundle=bundle)
        with patch('streamlit.download_button') as download:
            self.load(app)
        check=next((call for call in download.call_args_list if call.args[0]=='Download collection check JSON'),None)
        self.assertIsNotNone(check)
        evidence=json.loads(check.args[1])
        self.assertEqual(evidence['requested_sources'],['water_level'])
        self.assertEqual(evidence['collection_status'][0]['status'],'api_error')
        self.assertFalse(any(widget.label=='Download input snapshot CSV' for widget in app.get('download_button')))

    def test_without_raw_permission_does_not_offer_requests_or_expose_loaded_data(self):
        app = self.app(test_views={'weather', 'data_status'})
        self.assertNotIn('test_request_count', app.session_state)
        self.assertFalse(any(widget.label == 'Load selected records' for widget in app.button))
        self.assertTrue(any('raw-data access' in widget.value for widget in app.info))

    def test_changed_source_requires_reload_and_never_relabels_previous_snapshot(self):
        app = self.load(self.app())
        next(widget for widget in app.multiselect if widget.label == 'Sources to connect').set_value(['webtris']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['test_request_count'], 1)
        self.assertFalse(any(widget.label == 'Download input snapshot CSV' for widget in app.get('download_button')))
        self.assertTrue(any('Load selected records' in widget.value for widget in app.info))

    def test_traffic_has_no_implicit_timezone_conversion(self):
        app = self.load(self.app(integration_sources=['webtris']))
        self.assertTrue(any(widget.label == 'Traffic time assumption' for widget in app.selectbox))
        self.assertTrue(any('historical' in str(widget.value).lower() for widget in app.caption))
        self.assertEqual(next(widget for widget in app.selectbox if widget.label == 'Traffic time assumption').value,
                         'Unverified — keep blocked')

    def test_records_outside_requested_api_dates_do_not_enter_coverage(self):
        bundle = integration_fixture()
        bundle['webtris_daily']['timestamp'] = pd.Timestamp('2026-11-18T10:00:00')
        requested = (pd.Timestamp('2026-08-20').date(), pd.Timestamp('2026-08-21').date())
        app = self.load(self.app(test_bundle=bundle, integration_sources=['webtris'],
                                 integration_dates_traffic=requested))
        coverage = next(widget.value for widget in app.dataframe if 'Observation rows' in widget.value)
        self.assertEqual(coverage['Observation rows'].tolist(), [0])
        self.assertFalse(any(widget.label == 'Download input snapshot CSV'
                             for widget in app.get('download_button')))

    def test_series_labels_distinguish_datum_and_measure_and_select_exact_reference(self):
        from data_integration import normalise_observations
        bundle = integration_fixture()
        original = bundle['water_levels']
        local = original.assign(datum_uri='https://example.org/datum/local',
                                measure_uri='https://example.org/measure/local', value=9.1)
        alternative = original.assign(measure_uri='https://example.org/measure/alternative', value=2.2)
        bundle['water_levels'] = pd.concat([original, local, alternative], ignore_index=True)
        app = self.load(self.app(test_bundle=bundle))
        picker = next(widget for widget in app.multiselect if widget.label == 'Measurement series')
        self.assertEqual(len(set(picker.options)), 3)
        self.assertTrue(all('Tidal Level' in label and 'ref ' in label for label in picker.options))
        self.assertTrue(any('local' in label for label in picker.options))
        normalised = normalise_observations(bundle)
        local_id = normalised.loc[normalised['datum_uri'].eq('https://example.org/datum/local'), 'series_id'].iloc[0]
        picker.set_value([local_id]).run()
        self.assertFalse(app.exception)
        outputs = next(widget.value for widget in app.dataframe if 'age_minutes' in widget.value)
        self.assertEqual(outputs['datum_uri'].tolist(), ['https://example.org/datum/local'])
        self.assertEqual(outputs['value'].tolist(), [9.1])
        self.assertEqual(app.session_state['test_request_count'], 1)

    def test_handoff_retains_exact_reference_and_missing_reference_has_no_export(self):
        now = pd.Timestamp.now(tz='UTC').date().isoformat()
        context = {'source': 'water_level', 'source_id': 'HS004', 'station_reference': 'missing-station',
                   'unit': 'mAOD', 'datum_uri': 'datum:missing', 'start': now, 'end': now,
                   'entity_id': 'water:missing-station'}
        app = self.load(self.app(test_handoff=context))
        self.assertEqual(app.session_state['test_requested_sources'], ['water_level'])
        self.assertFalse(any(widget.label == 'Download input snapshot CSV' for widget in app.get('download_button')))
        self.assertTrue(any('requested reference' in widget.value for widget in app.info))


if __name__ == '__main__':
    unittest.main()
