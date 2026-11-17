import unittest

import pandas as pd

from model_inputs import build_model_inputs


def snapshot(**changes):
    row = {'source_id': 'HS004', 'source': 'water_level', 'entity_id': 'water:A',
           'series_id': 'water:series:A', 'metric': 'level', 'value': 1.2, 'unit': 'm',
           'datum_uri': 'datum:local', 'source_uri': 'https://example.org/reading/one',
           'event_time': pd.Timestamp('2026-11-01T10:00:00Z'),
           'available_at': pd.Timestamp('2026-11-01T10:02:00Z'),
           'cutoff': pd.Timestamp('2026-11-01T10:20:00Z'), 'status': 'Available',
           'time_basis': 'Offset-aware source timestamp',
           'availability_basis': 'Dashboard retrieval (not provider publication)'}
    row.update(changes)
    return pd.DataFrame([row])


def requirements(**changes):
    row = {'input_name': 'water_level', 'series_id': 'water:series:A',
           'expected_unit': 'm', 'required': True}
    row.update(changes)
    return pd.DataFrame([row])


class ModelInputTests(unittest.TestCase):
    def test_explicit_binding_keeps_one_row_and_per_feature_lineage(self):
        wide, checks = build_model_inputs(snapshot(), requirements(concept_ref='draft:level'))
        self.assertEqual(wide.columns.tolist(), ['cutoff', 'water_level'])
        self.assertEqual(wide.iloc[0]['water_level'], 1.2)
        self.assertTrue(checks.iloc[0]['passed'])
        self.assertEqual(checks.iloc[0]['entity_id'], 'water:A')
        self.assertEqual(checks.iloc[0]['source_id'], 'HS004')
        self.assertEqual(checks.iloc[0]['datum_uri'], 'datum:local')
        self.assertEqual(checks.iloc[0]['concept_ref'], 'draft:level')

    def test_unit_mismatch_never_converts_or_fills_a_value(self):
        wide, checks = build_model_inputs(snapshot(), requirements(expected_unit='mAOD'))
        self.assertTrue(pd.isna(wide.iloc[0]['water_level']))
        self.assertFalse(checks.iloc[0]['passed'])
        self.assertIn('unit', checks.iloc[0]['check'].lower())
        self.assertEqual(checks.iloc[0]['unit'], 'm')

    def test_missing_series_remains_explicit_even_if_optional(self):
        wide, checks = build_model_inputs(snapshot(), requirements(series_id='missing', required=False))
        self.assertTrue(pd.isna(wide.iloc[0]['water_level']))
        self.assertFalse(checks.iloc[0]['passed'])
        self.assertIn('missing', checks.iloc[0]['check'].lower())
        self.assertFalse(checks.iloc[0]['required'])

    def test_blocking_statuses_and_invalid_numeric_values_remain_missing(self):
        for status in ['Stale', 'Conflict', 'Invalid', 'Unknown']:
            with self.subTest(status=status):
                wide, checks = build_model_inputs(snapshot(status=status, value=5), requirements())
                self.assertTrue(pd.isna(wide.iloc[0]['water_level']))
                self.assertFalse(checks.iloc[0]['passed'])
                self.assertIn(status.lower(), checks.iloc[0]['check'].lower())
        for value in [float('inf'), float('nan'), True, 'invalid']:
            with self.subTest(value=value):
                wide, checks = build_model_inputs(snapshot(value=value), requirements())
                self.assertTrue(pd.isna(wide.iloc[0]['water_level']))
                self.assertFalse(checks.iloc[0]['passed'])

    def test_time_assumptions_require_explicit_opt_in_and_stay_labelled(self):
        assumed = snapshot(status='Available under time assumption', time_basis='User-assumed UTC (unverified)')
        blocked, checks = build_model_inputs(assumed, requirements())
        self.assertTrue(pd.isna(blocked.iloc[0]['water_level']))
        self.assertIn('assumption', checks.iloc[0]['check'])
        allowed, checks = build_model_inputs(assumed, requirements(), allow_time_assumptions=True)
        self.assertEqual(allowed.iloc[0]['water_level'], 1.2)
        self.assertEqual(checks.iloc[0]['status'], 'Available under time assumption')
        self.assertIn('assumption', checks.iloc[0]['check'])
        self.assertNotIn('approved', checks.iloc[0]['check'])

    def test_common_cutoff_is_timezone_aware_and_same_instant(self):
        same = pd.concat([snapshot(), snapshot(series_id='other', cutoff='2026-11-01T11:20:00+01:00')])
        wide, _ = build_model_inputs(same, requirements())
        self.assertEqual(wide.iloc[0]['cutoff'], pd.Timestamp('2026-11-01T10:20:00Z'))
        for bad in ['2026-11-01T10:21:00Z', '2026-11-01 10:20:00', None]:
            with self.subTest(cutoff=bad), self.assertRaisesRegex(ValueError, 'cut.off'):
                build_model_inputs(pd.concat([snapshot(), snapshot(series_id='other', cutoff=bad)]), requirements())

    def test_duplicate_snapshot_series_is_rejected_without_aggregation(self):
        with self.assertRaisesRegex(ValueError, 'series'):
            build_model_inputs(pd.concat([snapshot(), snapshot()]), requirements())

    def test_input_names_are_safe_unique_and_cannot_replace_metadata(self):
        for name in ['', ' ', 'cutoff', 'source_id', 'not safe', 'for', '_private']:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'input.name'):
                build_model_inputs(snapshot(), requirements(input_name=name))
        with self.assertRaisesRegex(ValueError, 'input.name'):
            build_model_inputs(snapshot(), pd.concat([requirements(), requirements()]))

    def test_required_flags_are_explicit_boolean_values(self):
        with self.assertRaisesRegex(ValueError, 'required'):
            build_model_inputs(snapshot(), requirements(required='False'))

    def test_time_permission_cannot_be_enabled_with_a_truthy_non_boolean(self):
        for value in ['False', 1, None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'allow_time_assumptions'):
                build_model_inputs(snapshot(), requirements(), allow_time_assumptions=value)

    def test_empty_snapshot_and_no_valid_values_never_zero_fill(self):
        wide, checks = build_model_inputs(snapshot().iloc[:0], requirements())
        self.assertEqual(len(wide), 1)
        self.assertTrue(pd.isna(wide.iloc[0]['water_level']))
        self.assertIn('missing', checks.iloc[0]['check'].lower())


if __name__ == '__main__':
    unittest.main()
