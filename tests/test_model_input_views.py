import json
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from test_model_inputs import snapshot


class ModelInputViewTests(unittest.TestCase):
    def app(self, frame=None, **state):
        app = AppTest.from_string("""import streamlit as st
from model_input_views import render_model_input_builder
if st.checkbox('Show model input builder', value=True, key='test_show_builder'):
    render_model_input_builder(st.session_state['test_records'], st.session_state['test_snapshot'],
        st.session_state['test_rules'])
""", default_timeout=30)
        frame = snapshot() if frame is None else frame
        app.session_state['test_records'] = frame.drop(columns=['cutoff', 'status']).assign(raw_record='{"original": true}')
        app.session_state['test_snapshot'] = frame
        app.session_state['test_rules'] = {'cutoff': '2026-11-01T10:20:00Z', 'availability_mode': 'retrieval',
                                         'freshness_minutes': 60}
        for key, value in state.items():
            app.session_state[key] = value
        return app

    def test_selected_series_form_a_wide_input_and_read_only_lineage(self):
        app = self.app().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Configured checks passed' in str(widget.value) for widget in app.success))
        editor = next(widget for widget in app.dataframe if 'input_name' in widget.value)
        self.assertEqual(editor.value['input_name'].tolist(), ['feature_1'])
        self.assertEqual(editor.value['series_id'].tolist(), ['water:series:A'])
        wide = next(widget.value for widget in app.dataframe if 'feature_1' in widget.value)
        self.assertEqual(wide.iloc[0]['feature_1'], 1.2)
        self.assertEqual(len(wide), 1)

    def test_exports_preserve_rules_cutoff_bindings_and_source_evidence(self):
        with patch('streamlit.download_button') as download:
            app = self.app().run()
        self.assertFalse(app.exception)
        package = next(call for call in download.call_args_list if call.args[0] == 'Download input contract JSON')
        contract = json.loads(package.args[1])
        self.assertEqual(contract['rules']['freshness_minutes'], 60)
        self.assertEqual(pd.Timestamp(contract['cutoff']), pd.Timestamp('2026-11-01T10:20:00Z'))
        self.assertIn('retrieval', contract['evidence_class'].lower())
        self.assertEqual(contract['checks'][0]['source_uri'], 'https://example.org/reading/one')
        self.assertEqual(contract['checks'][0]['datum_uri'], 'datum:local')
        self.assertEqual(contract['requirements'][0]['series_id'], 'water:series:A')
        self.assertEqual(contract['source_records'][0]['raw_record'], '{"original": true}')
        self.assertTrue(any(call.args[0] == 'Download model input CSV' for call in download.call_args_list))
        self.assertTrue(any(call.args[0] == 'Download input checks CSV' for call in download.call_args_list))

    def test_editor_configuration_is_used_without_changing_collected_records(self):
        import streamlit as st
        original = st.data_editor

        def editor(data, **kwargs):
            self.assertTrue({'series_id', 'metric', 'unit', 'datum_uri', 'entity_id', 'source_id'} <= set(kwargs['disabled']))
            return original(data.assign(expected_unit='mAOD'), **kwargs)

        with patch('streamlit.data_editor', editor):
            app = self.app().run()
        self.assertFalse(app.exception)
        wide = next(widget.value for widget in app.dataframe if 'feature_1' in widget.value)
        self.assertTrue(pd.isna(wide.iloc[0]['feature_1']))
        self.assertEqual(app.session_state['test_records'].iloc[0]['unit'], 'm')

    def test_replay_and_allowed_time_assumption_remain_explicit_in_export(self):
        frame = snapshot(status='Available under time assumption')
        rules = {'cutoff': '2026-11-01T10:20:00Z', 'availability_mode': 'replay', 'delay_minutes': 5}
        app = self.app(frame, test_rules=rules).run()
        checkbox = next(widget for widget in app.checkbox if 'time assumptions' in widget.label)
        with patch('streamlit.download_button') as download:
            checkbox.check().run()
        self.assertFalse(app.exception)
        contract = json.loads(next(call.args[1] for call in download.call_args_list
                                   if call.args[0] == 'Download input contract JSON'))
        self.assertIn('simulated', contract['evidence_class'].lower())
        self.assertTrue(contract['allow_time_assumptions'])
        self.assertEqual(contract['checks'][0]['status'], 'Available under time assumption')
        self.assertTrue(any('simulated' in str(widget.value).lower() for widget in app.caption))

    def test_empty_snapshot_offers_no_contract_or_editor(self):
        app = self.app(snapshot().iloc[:0]).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.get('download_button'))
        self.assertFalse(app.dataframe)

    def test_export_includes_evidence_for_only_the_explicitly_selected_series(self):
        records = pd.concat([snapshot(), snapshot(series_id='unselected', entity_id='water:B')])
        with patch('streamlit.download_button') as download:
            app = self.app(test_records=records).run()
        self.assertFalse(app.exception)
        contract = json.loads(next(call.args[1] for call in download.call_args_list
                                   if call.args[0] == 'Download input contract JSON'))
        self.assertEqual([row['series_id'] for row in contract['source_records']], ['water:series:A'])

    def test_editor_changes_survive_unmount_without_assigning_widget_state(self):
        app = self.app().run()
        editor = next(widget for widget in app.dataframe if 'input_name' in widget.value)
        editor_id = editor.proto.id
        # AppTest has no editor setter; send the same change payload as the browser.
        state = app._tree.get_widget_states()
        state.widgets.add(id=editor_id, string_value=json.dumps({
            'edited_rows': {'0': {'input_name': 'height', 'expected_unit': 'mAOD'}},
            'added_rows': [], 'deleted_rows': []}))
        app._run(state)
        self.assertFalse(app.exception)
        self.assertTrue(any('height' in widget.value for widget in app.dataframe))
        self.assertEqual(next(widget for widget in app.dataframe if 'input_name' in widget.value).proto.id,
                         editor_id)
        app.checkbox(key='test_show_builder').uncheck().run()
        self.assertFalse(app.exception)
        app.checkbox(key='test_show_builder').check().run()
        self.assertFalse(app.exception)
        editor = next(widget for widget in app.dataframe if 'input_name' in widget.value)
        self.assertEqual(editor.value['input_name'].tolist(), ['height'])
        self.assertEqual(editor.value['expected_unit'].tolist(), ['mAOD'])
        next(widget for widget in app.checkbox if 'time assumptions' in widget.label).check().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('height' in widget.value for widget in app.dataframe))


if __name__ == '__main__':
    unittest.main()
