import unittest

import pandas as pd

from validation_views import validation_register


class ValidationRegisterTests(unittest.TestCase):
    def setUp(self):
        self.catalog = pd.DataFrame([
            {'source_id': 'HS004', 'title': 'Water observations', 'domain': 'Water', 'access_level': 'Public'},
            {'source_id': 'HS011', 'title': 'Local operator data', 'domain': 'Operations', 'access_level': 'Unconfirmed'},
        ])
        self.report = {'sources': [
            {'source_id': 'HS004', 'temporal_role': 'Updated observations',
             'report_pages': [42, 43], 'evidence_status': 'report_assessment'},
            {'source_id': 'HS011', 'temporal_role': 'Unconfirmed local data',
             'report_pages': [], 'evidence_status': 'not_mapped'},
        ]}

    def test_report_assessment_and_connector_are_distinct_from_runtime_access(self):
        rows = validation_register(self.catalog, self.report, {'HS004'}).set_index('ID')
        self.assertEqual(rows.loc['HS004', 'Data role'], 'Updated observations')
        self.assertEqual(rows.loc['HS004', 'Report evidence'], 'Assessed in report')
        self.assertEqual(rows.loc['HS004', 'Dashboard route'], 'Connector available')
        self.assertEqual(rows.loc['HS004', 'Report pages'], '42, 43')
        self.assertNotIn('Live', rows.to_string())
        self.assertNotIn('Connected now', rows.to_string())

    def test_unmapped_source_does_not_gain_report_evidence(self):
        rows = validation_register(self.catalog, self.report, {'HS004'}).set_index('ID')
        self.assertEqual(rows.loc['HS011', 'Report evidence'], 'Mapping not confirmed')
        self.assertEqual(rows.loc['HS011', 'Report pages'], '')
        self.assertEqual(rows.loc['HS011', 'Dashboard route'], 'Reference / access pending')

    def test_missing_report_entry_remains_unknown_without_mutating_catalogue(self):
        original = self.catalog.copy(deep=True)
        rows = validation_register(self.catalog, {'sources': []}, set())
        self.assertEqual(set(rows['Data role']), {'Unconfirmed'})
        self.assertEqual(set(rows['Report evidence']), {'Mapping not confirmed'})
        pd.testing.assert_frame_equal(self.catalog, original)


if __name__ == '__main__':
    unittest.main()
