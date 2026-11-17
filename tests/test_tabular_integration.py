import io
import json
import unittest
import zipfile

import pandas as pd

from data_integration import RECORD_COLUMNS, integration_archive, integration_snapshot
from tabular_integration import map_tabular_observations, read_csv_upload


class TabularIntegrationTests(unittest.TestCase):
    content = b'id,reading,time\n001,1.2,2026-11-01T10:00:00Z\n'
    mapping = {'entity_id': 'id', 'value': 'reading', 'event_time': 'time'}
    metadata = {'metric': 'temperature', 'unit': 'degC', 'kind': 'generic'}
    collected = '2026-11-17T12:00:00Z'

    def records(self, content=None, metadata=None, mapping=None):
        return map_tabular_observations(read_csv_upload(content or self.content),
            mapping or self.mapping, metadata or self.metadata, self.collected)

    def test_csv_preserves_identifiers_literals_and_physical_row_numbers(self):
        frame = read_csv_upload(b'\xef\xbb\xbfid,reading,time,note\n001,NaN,2026-11-01T10:00:00Z,"first\nsecond"\n002,,bad,NA\n')
        self.assertEqual(frame['id'].tolist(), ['001', '002'])
        self.assertEqual(frame['reading'].tolist(), ['NaN', ''])
        self.assertEqual(frame['note'].iloc[1], 'NA')
        self.assertEqual(frame.attrs['csv_row_numbers'], [2, 4])
        self.assertEqual(len(frame.attrs['content_sha256']), 64)

    def test_single_large_field_within_file_limit_is_preserved(self):
        value = 'x' * 200000
        self.assertEqual(read_csv_upload(('note\n' + value + '\n').encode()).iloc[0]['note'], value)

    def test_rejects_bad_encoding_shape_headers_and_empty_csv(self):
        for content in [b'\xff', b'', b'a,a\n1,2\n', b'a,\n1,2\n', b'a,b\n1\n',
                        b'a,b\n1,2,3\n', b'a\n"unterminated', b'a\n', b'a\n\x00\n']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                read_csv_upload(content)

    def test_rejects_upload_limits_without_truncation(self):
        for content in [b'x' * (2 * 1024 * 1024 + 1),
                        (','.join('c' + str(i) for i in range(101)) + '\n').encode(),
                        b'id\n' + b'x\n' * 10001]:
            with self.subTest(size=len(content)), self.assertRaises(ValueError):
                read_csv_upload(content)
        self.assertEqual(len(read_csv_upload(b'id\n' + b'x\n' * 10000)), 10000)

    def test_canonical_rows_retain_upload_time_raw_fields_and_provisional_identity(self):
        records = self.records()
        self.assertEqual(records.columns.tolist(), RECORD_COLUMNS)
        row = records.iloc[0]
        self.assertEqual(row['entity_id'], 'csv:001')
        self.assertEqual(row['source'], 'csv_upload')
        self.assertEqual(row['value'], 1.2)
        self.assertEqual(row['available_at'], pd.Timestamp(self.collected))
        self.assertIn('upload', row['availability_basis'].lower())
        self.assertIn('provisional', row['quality_flags'])
        evidence = json.loads(row['raw_record'])
        self.assertEqual(evidence['csv_row_number'], 2)
        self.assertEqual(evidence['record']['id'], '001')
        self.assertEqual(row['measure_uri'], '')
        snapshot, audit = integration_snapshot(records, self.collected, freshness_minutes=10080)
        self.assertEqual(len(audit), 1)
        with zipfile.ZipFile(io.BytesIO(integration_archive(records, snapshot, audit, self.metadata))) as archive:
            self.assertIn('csv_row_number', archive.read('observations.csv').decode())

    def test_source_id_is_content_hash_and_original_frame_is_unchanged(self):
        frame = read_csv_upload(self.content)
        original = frame.copy(deep=True)
        records = map_tabular_observations(frame, self.mapping, self.metadata, self.collected)
        again = self.records(metadata=dict(self.metadata, source_label='Other label'))
        self.assertEqual(records.iloc[0]['source_id'], 'CSV:' + frame.attrs['content_sha256'])
        self.assertEqual(records.iloc[0]['source_id'], again.iloc[0]['source_id'])
        pd.testing.assert_frame_equal(frame, original)

    def test_no_historical_arrival_is_invented(self):
        snapshot, audit = integration_snapshot(self.records(), '2026-11-01T10:05:00Z')
        self.assertEqual(snapshot.iloc[0]['status'], 'Unknown')
        self.assertIn('Not yet available', audit.iloc[0]['exclusion_reason'])

    def test_invalid_rows_and_values_are_not_dropped_or_coerced(self):
        content = b'id,reading,time\nA,true,bad\n,NaN,2026-11-01T10:00:00Z\nB,inf,2026-11-01T10:00:00Z\nC,,2026-11-01T10:00:00Z\n'
        records = self.records(content)
        self.assertEqual(len(records), 4)
        self.assertTrue(records['value'].isna().all())
        self.assertTrue(records['quality_flags'].str.contains('invalid_value').all())
        self.assertIn('missing_entity', records.iloc[1]['quality_flags'])
        self.assertIn('invalid_event_time', records.iloc[0]['quality_flags'])
        frame = read_csv_upload(self.content)
        frame['reading'] = frame['reading'].astype(object)
        frame.loc[0, 'reading'] = True
        self.assertIn('invalid_value', map_tabular_observations(frame, self.mapping, self.metadata, self.collected).iloc[0]['quality_flags'])

    def test_timezone_is_explicit_and_london_dst_failures_remain_invalid(self):
        content = b'id,reading,time\nA,1,2026-07-01 12:00:00\nB,2,2026-10-25 01:30:00\nC,3,2026-03-29 01:30:00\n'
        records = self.records(content)
        self.assertTrue(records['event_time'].isna().all())
        self.assertTrue(records['quality_flags'].str.contains('unverified_timezone').all())
        assumed = self.records(content, dict(self.metadata, event_timezone='Europe/London'))
        self.assertEqual(assumed.iloc[0]['event_time'], pd.Timestamp('2026-07-01T11:00:00Z'))
        self.assertIn('assumed_timezone', assumed.iloc[0]['quality_flags'])
        self.assertTrue(assumed.iloc[1:]['event_time'].isna().all())
        self.assertTrue(assumed.iloc[1:]['quality_flags'].str.contains('invalid_event_time').all())

    def test_partial_and_relative_times_never_manufacture_observation_dates(self):
        invalid = ['10:00:00Z', 'now', 'today', '12:00', '2026', '2026-11-01',
                   '11/01/2026 10:00', '2026-11-01T10']
        content = ('id,reading,time\n' + ''.join(f'A,1,{value}\n' for value in invalid)).encode()
        for assumption in [None, 'UTC', 'Europe/London']:
            with self.subTest(assumption=assumption):
                records = self.records(content, dict(self.metadata, event_timezone=assumption))
                self.assertEqual(len(records), len(invalid))
                self.assertTrue(records['event_time'].isna().all())
                self.assertTrue(records['quality_flags'].str.contains('invalid_event_time').all())
                self.assertEqual(records['source_time'].tolist(), invalid)
                self.assertEqual([json.loads(row)['record']['time'] for row in records['raw_record']], invalid)
                snapshot, audit = integration_snapshot(records, self.collected)
                self.assertTrue(snapshot['status'].eq('Invalid').all())
                self.assertFalse(audit['included'].any())

    def test_complete_iso_dates_and_times_accept_minutes_seconds_fraction_and_offsets(self):
        valid = ['2026-11-01T10:00Z', '2026-11-01 11:00:00+01:00',
                 '2026-11-01T10:00:00.125+0000', '2026-11-01 10:00']
        content = ('id,reading,time\n' + ''.join(f'A,1,{value}\n' for value in valid)).encode()
        records = self.records(content, dict(self.metadata, event_timezone='UTC'))
        self.assertFalse(records['event_time'].isna().any())
        self.assertEqual(records.iloc[2]['event_time'], pd.Timestamp('2026-11-01T10:00:00.125Z'))
        self.assertIn('assumed_timezone', records.iloc[3]['quality_flags'])

    def test_column_metadata_distinguishes_units_datum_qualifier_and_concept(self):
        content = b'id,reading,time,metric,unit,datum,qualifier,concept\nA,1,2026-11-01T10:00:00Z,level,m,d:1,Tidal,c:1\nA,2,2026-11-01T10:00:00Z,level,m,d:2,Tidal,c:1\nA,3,2026-11-01T10:00:00Z,level,m,d:1,River,c:1\nA,4,2026-11-01T10:00:00Z,level,m,d:1,Tidal,c:2\nA,5,2026-11-01T10:00:00Z,level,cm,d:1,Tidal,c:1\n'
        mapping = dict(self.mapping, metric='metric', unit='unit', datum_uri='datum', qualifier='qualifier', concept_uri='concept')
        records = self.records(content, {'kind': 'water_level'}, mapping)
        self.assertEqual(records['series_id'].nunique(), 5)
        self.assertEqual(json.loads(records.iloc[0]['raw_record'])['declared_concept_uri'], 'c:1')

    def test_mapping_and_water_level_declarations_are_required(self):
        frame = read_csv_upload(self.content)
        for mapping, metadata, time in [({}, self.metadata, self.collected),
            (dict(self.mapping, value='absent'), self.metadata, self.collected),
            (self.mapping, {'metric': 'level'}, self.collected),
            (self.mapping, dict(self.metadata, kind='water_level'), self.collected),
            (self.mapping, dict(self.metadata, event_timezone='America/New_York'), self.collected),
            (self.mapping, self.metadata, '2026-11-17 12:00:00')]:
            with self.subTest(metadata=metadata, mapping=mapping), self.assertRaises(ValueError):
                map_tabular_observations(frame, mapping, metadata, time)

    def test_missing_mapped_water_datum_stays_invalid(self):
        content = b'id,reading,time,datum\nA,1,2026-11-01T10:00:00Z,\n'
        records = self.records(content, dict(self.metadata, kind='water_level', qualifier='Tidal'),
                               dict(self.mapping, datum_uri='datum'))
        self.assertIn('missing_datum', records.iloc[0]['quality_flags'])
        self.assertEqual(integration_snapshot(records, self.collected)[0].iloc[0]['status'], 'Invalid')


if __name__ == '__main__':
    unittest.main()
