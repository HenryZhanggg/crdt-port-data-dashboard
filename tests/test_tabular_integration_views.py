import io
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class TabularIntegrationViewTests(unittest.TestCase):
    content = b'id,reading,time\n001,1.2,2026-11-01T10:00:00Z\n'

    def app(self, content=None, views=None, **state):
        app = AppTest.from_string('''import streamlit as st
from tabular_integration_views import render_csv_mapping
result = render_csv_mapping(st.session_state.get('test_views', {'raw_data'}))
st.session_state['test_returned'] = result
''', default_timeout=30)
        app.session_state['test_views'] = views if views is not None else {'raw_data'}
        for key, value in state.items():
            app.session_state[key] = value
        self.rerun(app, content)
        return app

    def rerun(self, app, content=None):
        uploaded = None
        if content is not None:
            uploaded = io.BytesIO(content)
            uploaded.name = 'observations.csv'
        with patch('streamlit.file_uploader', return_value=uploaded) as uploader:
            app.run()
        self.assertFalse(app.exception)
        return uploader

    def map(self, app):
        for key, value in [('integration_csv_entity_id_column', 'id'),
                           ('integration_csv_value_column', 'reading'),
                           ('integration_csv_event_time_column', 'time')]:
            app.selectbox(key=key).set_value(value)
        app.text_input(key='integration_csv_metric_constant').set_value('temperature')
        app.text_input(key='integration_csv_unit_constant').set_value('degC')
        next(widget for widget in app.button if widget.label == 'Apply column mapping').click()
        self.rerun(app, self.content)

    def test_without_raw_permission_has_no_upload_or_loaded_records(self):
        app = self.app(self.content, views={'weather'})
        self.assertIsNone(app.session_state['test_returned'])
        self.assertFalse(app.get('file_uploader'))
        self.assertFalse(app.button)
        self.assertTrue(any('raw-data access' in item.value for item in app.info))

    def test_preview_does_not_map_automatically_and_requires_explicit_columns(self):
        app = self.app(self.content)
        self.assertIsNone(app.session_state['test_returned'])
        self.assertEqual(app.dataframe[0].value.iloc[0]['id'], '001')
        self.assertTrue(any('ISO 8601' in item.value for item in app.caption))
        self.assertIsNone(app.selectbox(key='integration_csv_entity_id_column').value)
        next(widget for widget in app.button if widget.label == 'Apply column mapping').click()
        self.rerun(app, self.content)
        self.assertTrue(any('entity_id' in item.value for item in app.error))

    def test_mapping_is_exportable_retained_in_session_and_clearable(self):
        app = self.app(self.content)
        seen_time = app.session_state['integration_csv_seen']['collected_at']
        self.map(app)
        records, metadata = app.session_state['test_returned']
        self.assertEqual(len(records), 1)
        self.assertEqual(metadata['mapped_at'], seen_time)
        self.assertEqual(metadata['original_row_count'], 1)
        self.assertEqual(metadata['column_mapping']['entity_id'], 'id')
        self.assertEqual(metadata['source_id'], records.iloc[0]['source_id'])
        self.assertEqual(metadata['requested_sources'], ['csv_upload'])
        self.assertEqual(metadata['collection_status'][0]['records'], 1)
        self.assertIsNone(metadata['observation_context'])
        self.assertEqual(records.iloc[0]['available_at'].isoformat(), seen_time)
        self.rerun(app)
        self.assertIsNotNone(app.session_state['test_returned'])
        self.assertTrue(any('still loaded' in item.value for item in app.info))
        next(widget for widget in app.button if widget.label == 'Clear uploaded records').click()
        self.rerun(app)
        self.assertIsNone(app.session_state['test_returned'])
        self.assertNotIn('integration_upload_records', app.session_state)

    def test_new_or_invalid_file_cannot_return_previous_mapping(self):
        app = self.app(self.content)
        self.map(app)
        self.rerun(app, b'id,reading,time\nB,2,2026-11-01T10:00:00Z\n')
        self.assertIsNone(app.session_state['test_returned'])
        self.assertNotIn('integration_upload_records', app.session_state)
        self.rerun(app, b'a,b\n1,2,3\n')
        self.assertTrue(app.error)
        self.assertIsNone(app.session_state['test_returned'])

    def test_changed_mapping_requires_apply_and_water_requires_datum(self):
        app = self.app(self.content)
        self.map(app)
        app.text_input(key='integration_csv_unit_constant').set_value('K')
        self.rerun(app, self.content)
        self.assertIsNone(app.session_state['test_returned'])
        app.selectbox(key='integration_csv_kind').set_value('water_level')
        next(widget for widget in app.button if widget.label == 'Apply column mapping').click()
        self.rerun(app, self.content)
        self.assertTrue(any('datum_uri' in item.value for item in app.error))


if __name__ == '__main__':
    unittest.main()
