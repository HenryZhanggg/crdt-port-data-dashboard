import io
import json
import unittest
import zipfile

import pandas as pd

from data_integration import integration_archive, integration_snapshot, normalise_observations


def water(**changes):
    row = {'station_reference': 'A', 'parameter': 'level', 'qualifier': 'Tidal Level',
           'unit': 'm', 'datum_uri': 'datum:local', 'measure_uri': 'https://example.org/measure/A',
           'reading_uri': 'https://example.org/reading/one', 'value': 1.2,
           'date_time': '2026-11-01T10:00:00Z', 'retrieved_at_utc': '2026-11-01T10:02:00Z'}
    row.update(changes)
    return row


class IntegrationTests(unittest.TestCase):
    def records(self, *rows):
        return normalise_observations({'water_levels': pd.DataFrame(rows)})

    def test_reference_identity_and_original_evidence_survive_normalisation(self):
        raw = pd.DataFrame([water(), water(unit='mAOD'), water(datum_uri='datum:aod'),
                            water(measure_uri='https://example.org/measure/other'),
                            water(qualifier='River Level')])
        original = raw.copy(deep=True)
        records = normalise_observations({'water_levels': raw})
        self.assertEqual(records['series_id'].nunique(), 5)
        self.assertEqual(set(records['entity_id']), {'water:A'})
        self.assertEqual(records.iloc[0]['source_uri'], 'https://example.org/reading/one')
        self.assertEqual(json.loads(records.iloc[0]['raw_record'])['measure_uri'], water()['measure_uri'])
        pd.testing.assert_frame_equal(raw, original)

    def test_counter_identity_is_stable_after_numeric_merge_coercion(self):
        frame=pd.DataFrame([
            {'site_id': '6806', 'timestamp': '2026-11-01T10:00:00Z', 'Total Volume': 20},
            {'site_id': 6806.0, 'timestamp': '2026-11-01T10:15:00Z', 'Total Volume': 21},
        ])
        records=normalise_observations({'webtris_daily': frame})
        self.assertEqual(set(records['entity_id']), {'traffic:6806'})
        self.assertEqual(records['series_id'].nunique(), 1)

    def test_traffic_preserves_actual_connector_endpoint_as_source_evidence(self):
        endpoint='https://webtris.highwaysengland.co.uk/api/v1.0/reports/Daily?sites=6806'
        records=normalise_observations({
            'webtris_daily': pd.DataFrame([{'site_id': '6806', 'timestamp': '2026-11-01T10:00:00Z', 'Total Volume': 20}]),
            'status': pd.DataFrame([{'connector_id': 'webtris_daily_a5036_api',
                'api_endpoint': endpoint, 'last_call_utc': '2026-11-01T10:02:00Z'}]),
        })
        self.assertEqual(records.iloc[0]['source_uri'], endpoint)

    def test_unverified_traffic_timezone_is_blocked_and_assumption_is_retained(self):
        bundle = {'webtris_daily': pd.DataFrame([{'site_id': '6806', 'timestamp': '2026-07-01 12:00:00',
                   'Total Volume': 20, 'retrieved_at_utc': '2026-07-01T12:01:00Z'}])}
        records = normalise_observations(bundle)
        self.assertTrue(pd.isna(records.iloc[0]['event_time']))
        self.assertIn('unverified_timezone', records.iloc[0]['quality_flags'])
        snapshot, _ = integration_snapshot(records, '2026-07-01T12:05:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Invalid')
        assumed = normalise_observations(bundle, traffic_timezone='Europe/London')
        self.assertEqual(assumed.iloc[0]['event_time'], pd.Timestamp('2026-07-01T11:00:00Z'))
        snapshot, _ = integration_snapshot(assumed, '2026-07-01T12:05:00Z', freshness_minutes=90)
        self.assertEqual(snapshot.iloc[0]['status'], 'Available under time assumption')
        self.assertIn('assumed', snapshot.iloc[0]['time_basis'].lower())

    def test_retrieval_cutoff_does_not_pretend_historical_publication_is_known(self):
        records = self.records(water(retrieved_at_utc='2026-11-01T11:00:00Z'))
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:30:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Unknown')
        self.assertTrue(pd.isna(snapshot.iloc[0]['value']))
        self.assertFalse(audit.iloc[0]['included'])
        self.assertIn('retrieval', records.iloc[0]['availability_basis'].lower())
        replay, audit = integration_snapshot(records, '2026-11-01T10:30:00Z', availability_mode='replay')
        self.assertEqual(replay.iloc[0]['value'], 1.2)
        self.assertIn('simulated', audit.iloc[0]['availability_basis'].lower())

    def test_stale_value_remains_missing_and_future_records_are_excluded(self):
        records = self.records(water(), water(date_time='2026-11-01T14:00:00Z', value=9))
        snapshot, audit = integration_snapshot(records, '2026-11-01T12:00:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Stale')
        self.assertTrue(pd.isna(snapshot.iloc[0]['value']))
        self.assertEqual(snapshot.iloc[0]['last_value'], 1.2)
        self.assertIn('Future event', audit.iloc[1]['exclusion_reason'])

    def test_latest_conflict_never_arbitrarily_selects_a_value(self):
        records = self.records(water(), water(date_time='2026-11-01T10:15:00Z', value=2),
                               water(date_time='2026-11-01T10:15:00Z', value=3))
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Conflict')
        self.assertTrue(pd.isna(snapshot.iloc[0]['value']))
        self.assertFalse(audit['selected'].any())
        self.assertEqual(len(audit), 3)

    def test_exact_duplicates_are_audited_without_creating_a_conflict(self):
        records = self.records(water(), water())
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Available')
        self.assertEqual(snapshot.iloc[0]['value'], 1.2)
        self.assertEqual(int(audit['selected'].sum()), 1)
        self.assertTrue(audit['exclusion_reason'].str.contains('Exact duplicate').any())

    def test_replay_delay_and_missing_policy_leave_explicit_unknown_outputs(self):
        records = self.records(water())
        delayed, _ = integration_snapshot(records, '2026-11-01T10:05:00Z', availability_mode='replay', delay_minutes=10)
        self.assertEqual(delayed.iloc[0]['status'], 'Unknown')
        missing, audit = integration_snapshot(records, '2026-11-01T10:20:00Z', availability_mode='replay', drop_every=1)
        self.assertEqual(missing.iloc[0]['status'], 'Unknown')
        self.assertIn('Simulated missing', audit.iloc[0]['exclusion_reason'])

    def test_simulated_loss_of_one_duplicate_does_not_discard_the_delivered_copy(self):
        records = self.records(water(date_time='2026-11-01T09:45:00Z', value=0.3), water(), water())
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z',
                                                availability_mode='replay', drop_every=2)
        self.assertEqual(snapshot.iloc[0]['status'], 'Available')
        self.assertEqual(snapshot.iloc[0]['value'], 1.2)
        self.assertEqual(int(audit['selected'].sum()), 1)

    def test_later_conflicting_record_does_not_change_an_earlier_cutoff(self):
        records = self.records(water(), water(value=3, retrieved_at_utc='2026-11-01T10:10:00Z'))
        early, _ = integration_snapshot(records, '2026-11-01T10:05:00Z')
        later, _ = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertEqual(early.iloc[0]['value'], 1.2)
        self.assertEqual(later.iloc[0]['status'], 'Conflict')

    def test_unknown_collection_time_is_not_invented_from_observation_time(self):
        records = self.records(water(retrieved_at_utc=None))
        snapshot, _ = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Unknown')
        self.assertTrue(pd.isna(records.iloc[0]['available_at']))

    def test_invalid_values_and_metadata_remain_in_the_audit(self):
        records = self.records(water(value=float('inf')), water(station_reference='', value=True))
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertEqual(set(snapshot['status']), {'Invalid'})
        self.assertTrue(snapshot['value'].isna().all())
        self.assertEqual(len(audit), 2)
        self.assertIn('invalid_value', audit.iloc[0]['quality_flags'])
        self.assertIn('missing_entity', audit.iloc[1]['quality_flags'])

    def test_configuration_rejects_naive_cutoff_and_invalid_parameters(self):
        records = self.records(water())
        for options in [{'cutoff': '2026-11-01 10:20:00'},
                        {'cutoff': '2026-11-01T10:20:00Z', 'freshness_minutes': 0},
                        {'cutoff': '2026-11-01T10:20:00Z', 'delay_minutes': -1},
                        {'cutoff': '2026-11-01T10:20:00Z', 'drop_every': 1.5},
                        {'cutoff': '2026-11-01T10:20:00Z', 'availability_mode': 'unverified'}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                integration_snapshot(records, **options)

    def test_archive_has_reproducible_inputs_rules_and_evidence_boundaries(self):
        records = self.records(water())
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z')
        data = integration_archive(records, snapshot, audit, {'cutoff': '2026-11-01T10:20:00Z', 'availability_mode': 'retrieval'})
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertTrue({'observations.csv', 'snapshot.csv', 'audit.csv', 'rules.json', 'README.txt'} <= set(archive.namelist()))
            self.assertEqual(json.loads(archive.read('rules.json'))['cutoff'], '2026-11-01T10:20:00Z')
            self.assertIn('not provider publication', archive.read('README.txt').decode())
            self.assertIn('https://example.org/reading/one', archive.read('audit.csv').decode())

    def test_empty_input_keeps_exportable_shapes(self):
        records = normalise_observations({})
        snapshot, audit = integration_snapshot(records, '2026-11-01T10:20:00Z')
        self.assertTrue(records.empty and snapshot.empty and audit.empty)
        self.assertIn('series_id', snapshot)
        self.assertIn('exclusion_reason', audit)


if __name__ == '__main__':
    unittest.main()
