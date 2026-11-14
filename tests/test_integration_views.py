import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from test_dashboard_views import observation_fixture


class IntegrationViewTests(unittest.TestCase):
    def open_demo(self):
        st.cache_data.clear()
        fetch = patch('api_connectors.fetch_raw_data_bundle', return_value=observation_fixture())
        fetch.start()
        self.addCleanup(fetch.stop)
        app = AppTest.from_file('app.py', default_timeout=30)
        app.session_state['dashboard_authorised'] = True
        app.run()
        next(x for x in app.radio if x.label == 'Workspace').set_value('WP Delivery').run()
        view = next(x for x in app.radio if x.label == 'View')
        self.assertIn('Integration Demo', view.options)
        view.set_value('Integration Demo').run()
        self.assertFalse(app.exception)
        return app

    def test_demo_explains_three_levels_and_preserves_partner_results(self):
        app = self.open_demo()
        self.assertTrue(any(x.label == 'Connection example' for x in app.selectbox))
        content = ' '.join(str(x.value) for x in list(app.markdown) + list(app.caption) + list(app.info))
        for phrase in ['Shared viewing', 'Data handover', 'Linked execution', 'illustrative']:
            self.assertIn(phrase, content)
        self.assertFalse(app.session_state.filtered_state.get('partner_runs', {}))
        self.assertFalse(app.session_state.filtered_state.get('partner_dependencies', {}))

    def test_missing_input_blocks_preview_without_zero_fill(self):
        app = self.open_demo()
        next(x for x in app.selectbox if x.label == 'Connection example').set_value('missing_input').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Blocked' in str(x.value) for x in app.error))
        next(x for x in app.button if x.label == 'Preview execution order').click().run()
        self.assertFalse(app.exception)
        tables = [str(x.value.to_dict()) for x in app.dataframe]
        self.assertTrue(any('Blocked' in x for x in tables))
        self.assertFalse(app.session_state.filtered_state.get('partner_runs', {}))

    def test_aligned_metadata_keeps_acceptance_pending(self):
        app = self.open_demo()
        next(x for x in app.selectbox if x.label == 'Connection example').set_value('aligned').run()
        next(x for x in app.button if x.label == 'Preview execution order').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('acceptance' in str(x.value).lower() for x in app.info))
        tables = ' '.join(str(x.value.to_dict()) for x in app.dataframe)
        self.assertIn('Review', tables)
        self.assertFalse(app.session_state.filtered_state.get('partner_runs', {}))

    def test_equal_units_with_different_reference_are_blocked(self):
        app = self.open_demo()
        next(x for x in app.selectbox if x.label == 'Connection example').set_value('reference_mismatch').run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Blocked' in str(x.value) for x in app.error))

    def test_delivery_roles_cover_all_wps_and_drafts_can_be_downloaded(self):
        app = self.open_demo()
        tables = ' '.join(str(x.value.to_dict()) for x in app.dataframe)
        for wp in range(1, 8):
            self.assertIn(f'WP{wp}', tables)
        labels = [x.label for x in app.get('download_button')]
        self.assertIn('Download this connection draft', labels)
        self.assertIn('Download partner handover template', labels)


if __name__ == '__main__':
    unittest.main()
