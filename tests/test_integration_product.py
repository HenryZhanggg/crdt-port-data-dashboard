import importlib.util
import json
import unittest

import pandas as pd
from data_integration import RECORD_COLUMNS, integration_snapshot


class IntegrationProductTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('integration_product'), 'Explicit linkage service is required')
        import integration_product
        return integration_product

    def records(self):
        row={name:'' for name in RECORD_COLUMNS}
        row.update(source_id='HS004',source='water_level',entity_id='water:A',series_id='water:series:A',
            metric='level',value=1.2,unit='mAOD',datum_uri='datum:aod',qualifier='Tidal Level',
            event_time=pd.Timestamp('2026-11-18T10:00:00Z'),available_at=pd.Timestamp('2026-11-18T10:05:00Z'),
            raw_record=' { "original": true, "value": 1.20 } ')
        return pd.DataFrame([row,{**row,'source_id':'CSV:hash','source':'csv_upload','entity_id':'csv:A','series_id':'csv:series:A'}])

    def confirmed(self,records):
        bindings=self.api().integration_bindings(records)
        return bindings.assign(common_entity_id='port:station-A',common_concept='urn:level',confirmed=True)

    def test_default_bindings_are_stable_and_unconfirmed(self):
        records=self.records();api=self.api()
        bindings=api.integration_bindings(pd.concat([records,records.iloc[:1]]))
        pd.testing.assert_frame_equal(bindings,api.integration_bindings(records.iloc[::-1]))
        self.assertEqual(len(bindings),2);self.assertFalse(bindings['confirmed'].any())
        self.assertEqual(set(bindings['source_entity_id']),{'water:A','csv:A'})

    def test_only_explicit_matching_meaning_groups_api_and_csv(self):
        records=self.records();mapped,links=self.api().apply_integration_bindings(records,self.confirmed(records))
        self.assertEqual(mapped['series_id'].nunique(),1)
        self.assertTrue(mapped['entity_id'].eq('port:station-A').all())
        self.assertTrue(links['group_source_count'].eq(2).all())
        self.assertTrue(links['status'].eq('mapped').all())
        retained=[x for x in RECORD_COLUMNS if x not in {'entity_id','metric','series_id','raw_record'}]
        pd.testing.assert_frame_equal(records[retained],mapped[retained])

    def test_unconfirmed_and_incomplete_declarations_do_not_merge(self):
        records=self.records();api=self.api()
        examples=[self.confirmed(records).assign(confirmed=False),pd.DataFrame()]
        examples += [self.confirmed(records).assign(**{field:blank}) for field in ['common_entity_id','common_concept'] for blank in ['',None,'  ']]
        for bindings in examples:
            with self.subTest(bindings=bindings.to_json(orient='records')):
                mapped,links=api.apply_integration_bindings(records,bindings)
                pd.testing.assert_frame_equal(mapped[RECORD_COLUMNS],records[RECORD_COLUMNS])
                self.assertTrue(links['status'].eq('unmatched').all())

    def test_incompatible_units_datums_and_qualifiers_stay_separate(self):
        for field,value in [('unit','mODN'),('datum_uri','datum:other'),('qualifier','Groundwater'),('unit',' mAOD')]:
            with self.subTest(field=field,value=value):
                records=self.records();records.loc[1,field]=value
                mapped,links=self.api().apply_integration_bindings(records,self.confirmed(records))
                self.assertEqual(mapped['series_id'].nunique(),2)
                self.assertTrue(links['status'].eq('incompatible').all())
                self.assertTrue(links['reason'].str.contains(field).all())
                pd.testing.assert_series_equal(mapped[field],records[field])

    def test_source_evidence_is_exact_and_input_is_not_mutated(self):
        records=self.records();records.index=[7,7];original=records.copy(deep=True)
        mapped,_=self.api().apply_integration_bindings(records,self.confirmed(records))
        pd.testing.assert_frame_equal(records,original)
        for position,raw in enumerate(mapped['raw_record']):
            evidence=json.loads(raw);source=original.iloc[position]
            self.assertEqual(evidence['original_raw_record'],source['raw_record'])
            self.assertEqual(evidence['integration_product']['source_series_id'],source['series_id'])
            self.assertEqual(mapped.iloc[position]['source_entity_id'],source['entity_id'])

    def test_duplicate_unknown_and_nonboolean_bindings_are_rejected(self):
        records=self.records();api=self.api();bindings=self.confirmed(records)
        cases=[pd.concat([bindings,bindings.iloc[:1]]),bindings.assign(series_id='unknown')]
        cases += [bindings.assign(confirmed=value) for value in ['true',1,0,None]]
        for invalid in cases:
            with self.subTest(bindings=invalid.to_json(orient='records')):
                with self.assertRaises(ValueError):api.apply_integration_bindings(records,invalid)

    def test_ambiguous_source_or_forged_binding_metadata_is_rejected(self):
        records=self.records();api=self.api();bindings=self.confirmed(records)
        conflict=pd.concat([records,records.iloc[:1].assign(unit='mODN')])
        with self.assertRaises(ValueError):api.apply_integration_bindings(conflict,bindings)
        with self.assertRaises(ValueError):api.apply_integration_bindings(records,bindings.assign(unit='mODN'))

    def test_group_ids_are_deterministic_and_source_count_is_distinct(self):
        records=self.records();records=pd.concat([records,records.iloc[:1].assign(series_id='water:other')],ignore_index=True)
        api=self.api();mapped,links=api.apply_integration_bindings(records,self.confirmed(records))
        reverse,reverse_links=api.apply_integration_bindings(records.iloc[::-1],self.confirmed(records).iloc[::-1])
        pd.testing.assert_frame_equal(links,reverse_links)
        self.assertEqual(mapped['series_id'].tolist(),reverse['series_id'].tolist()[::-1])
        self.assertTrue(links['group_source_count'].eq(2).all());self.assertTrue(links['group_series_count'].eq(3).all())

    def test_joint_snapshot_retains_conflicts_and_invalid_values_as_missing(self):
        records=self.records();records.loc[1,'value']=9.5
        mapped,_=self.api().apply_integration_bindings(records,self.confirmed(records))
        snapshot,_=integration_snapshot(mapped,'2026-11-18T10:10:00Z')
        self.assertEqual(snapshot['status'].tolist(),['Conflict']);self.assertTrue(snapshot['value'].isna().all())
        records['value']=float('nan');records['quality_flags']='invalid_value'
        mapped,_=self.api().apply_integration_bindings(records,self.confirmed(records))
        snapshot,_=integration_snapshot(mapped,'2026-11-18T10:10:00Z')
        self.assertTrue(snapshot['value'].isna().all())
