import unittest

import pandas as pd


from data_relations import build_data_relations, nearby_candidates


def water_context(**changes):
    context = {'source': 'water_level', 'source_id': 'HS004', 'entity_id': 'water:A',
               'station_reference': 'A', 'unit': 'm', 'datum_uri': 'datum:local',
               'start': '2026-10-01', 'end': '2026-10-01'}
    context.update(changes)
    return context


def water_row(**changes):
    row = {'station_reference': 'A', 'parameter': 'level', 'qualifier': 'Tidal Level',
           'unit': 'm', 'datum_uri': 'datum:local', 'value': 1.2,
           'date_time': '2026-10-01T12:00:00Z', 'lat': 53.448, 'lon': -3.015,
           'api_endpoint': 'https://example.org/readings?station=A',
           'retrieved_at_utc': '2026-10-02T10:00:00Z'}
    row.update(changes)
    return row


def nodes(model, kind):
    return [node for node in model['nodes'] if node['kind'] == kind]


class DataRelationsTests(unittest.TestCase):
    def test_exact_reference_date_and_raw_duplicates_survive_without_mutation(self):
        frame = pd.DataFrame([water_row(), water_row(), water_row(value=8.0),
                              water_row(station_reference='B'), water_row(datum_uri='datum:aod'),
                              water_row(unit='mAOD'), water_row(date_time='2026-10-02T00:00:00Z')])
        original = frame.copy(deep=True)
        model = build_data_relations({'water_levels': frame}, water_context())
        pd.testing.assert_frame_equal(frame, original)
        self.assertEqual(model['metadata']['actual_record_count'], 3)
        self.assertEqual(model['metadata']['selected_object'], 'water:A')
        self.assertEqual(model['metadata']['reference']['datum_uri'], 'datum:local')
        self.assertEqual(nodes(model, 'Records')[0]['detail']['exact_duplicate_count'], 1)
        self.assertEqual(nodes(model, 'Records')[0]['detail']['conflicting_timestamp_count'], 1)
        self.assertTrue(any('conflict' in gap.lower() for gap in model['gaps']))
        self.assertEqual({edge['relation'] for edge in model['edges']},
                         {'returnsRecords', 'recordsInSeries', 'recordedFor'})
        source = nodes(model, 'Source')[0]
        self.assertEqual(source['id'], 'source:ea_liverpool_tide_water_level_api')
        self.assertEqual(next(edge for edge in model['edges'] if edge['relation'] == 'returnsRecords')['source'], source['id'])
        self.assertEqual(nodes(model, 'Object')[0]['id'], 'water:A')

    def test_property_qualifier_and_authoritative_measure_ids_keep_series_separate(self):
        frame = pd.DataFrame([water_row(measure_uri='measure:one'), water_row(measure_uri='measure:two'),
                              water_row(parameter='temperature', measure_uri='measure:one'),
                              water_row(qualifier='River Level', measure_uri='measure:one')])
        model = build_data_relations({'water_levels': frame}, water_context())
        self.assertEqual(len(nodes(model, 'Series')), 4)
        self.assertEqual(len({node['id'] for node in nodes(model, 'Series')}), 4)
        self.assertEqual(len(nodes(model, 'Records')), 4)
        self.assertEqual({node['detail']['measure_uri'] for node in nodes(model, 'Series')},
                         {'measure:one', 'measure:two'})

    def test_snapshot_ids_ignore_row_order_but_include_duplicates_and_values(self):
        frame = pd.DataFrame([water_row(), water_row(date_time='2026-10-01T12:15:00Z')])
        base = build_data_relations({'water_levels': frame}, water_context())
        reordered = build_data_relations({'water_levels': frame.iloc[::-1]}, water_context())
        self.assertEqual(base, reordered)
        duplicates = build_data_relations({'water_levels': pd.concat([frame, frame.iloc[[0]]])}, water_context())
        changed = build_data_relations({'water_levels': frame.assign(value=3)}, water_context())
        self.assertEqual(nodes(base, 'Series')[0]['id'], nodes(changed, 'Series')[0]['id'])
        self.assertNotEqual(nodes(base, 'Records')[0]['id'], nodes(changed, 'Records')[0]['id'])
        self.assertNotEqual(nodes(base, 'Records')[0]['id'], nodes(duplicates, 'Records')[0]['id'])
        self.assertEqual(duplicates['metadata']['actual_record_count'], 3)

    def test_missing_identity_values_stay_unknown_and_provisional(self):
        frame = pd.DataFrame([water_row(parameter=None, qualifier='', datum_uri=None)])
        model = build_data_relations({'water_levels': frame}, water_context(datum_uri=''))
        detail = nodes(model, 'Series')[0]['detail']
        self.assertEqual(detail['parameter'], '')
        self.assertEqual(detail['qualifier'], '')
        self.assertEqual(detail['datum_uri'], '')
        self.assertEqual(detail['measure_uri'], '')
        self.assertIn('provisional', model['metadata']['identity_note'].lower())
        self.assertTrue(any('parameter' in gap and 'datum_uri' in gap for gap in model['gaps']))
        self.assertTrue(any('measure_uri' in gap for gap in model['gaps']))

    def test_source_uris_are_retained_without_creating_reading_ids(self):
        frame = pd.DataFrame([water_row(station_uri='https://example.org/stations/A',
                                       measure_uri='https://example.org/measures/A-level',
                                       reading_uri='https://example.org/readings/one')])
        model = build_data_relations({'water_levels': frame}, water_context())
        self.assertEqual(nodes(model, 'Object')[0]['detail'].get('station_uri'), 'https://example.org/stations/A')
        self.assertEqual(nodes(model, 'Records')[0]['detail']['reading_sources'], 'https://example.org/readings/one')
        self.assertEqual(len(model['nodes']), 4)
        self.assertFalse(any('measure_uri' in gap for gap in model['gaps']))

    def test_unit_and_datum_are_part_of_series_identity(self):
        frame = pd.DataFrame([water_row(), water_row(unit='mAOD'), water_row(datum_uri='datum:aod')])
        local = build_data_relations({'water_levels': frame}, water_context())
        other_unit = build_data_relations({'water_levels': frame}, water_context(unit='mAOD'))
        other_datum = build_data_relations({'water_levels': frame}, water_context(datum_uri='datum:aod'))
        self.assertEqual(len({nodes(model, 'Series')[0]['id'] for model in [local, other_unit, other_datum]}), 3)
        self.assertEqual({nodes(model, 'Object')[0]['id'] for model in [local, other_unit, other_datum]}, {'water:A'})

    def test_source_provenance_uses_selected_connector_and_source_timestamps(self):
        status = pd.DataFrame([
            {'connector_id': 'ea_liverpool_tide_water_level_api', 'api_endpoint': 'https://example.org/product',
             'last_call_utc': '2026-10-02T11:00:00Z'},
            {'connector_id': 'webtris_daily_a5036_api', 'api_endpoint': 'https://example.org/other',
             'last_call_utc': '2026-10-03T11:00:00Z'}])
        model = build_data_relations({'water_levels': pd.DataFrame([water_row()]), 'status': status}, water_context())
        metadata = model['metadata']
        self.assertEqual(metadata['checked_at'], '2026-10-02T11:00:00Z')
        self.assertEqual(metadata['source_endpoint'], 'https://example.org/readings?station=A')
        self.assertEqual(metadata['first_observed'], '2026-10-01T12:00:00Z')
        self.assertEqual(metadata['latest_observed'], '2026-10-01T12:00:00Z')
        self.assertEqual(metadata['time_basis'], 'UTC')
        self.assertEqual(metadata['requested_start'], '2026-10-01')
        self.assertTrue(all(edge['evidence_ref'] for edge in model['edges']))

    def test_nonzero_offset_stays_explicit_without_becoming_utc_or_unverified(self):
        frame = pd.DataFrame([water_row(date_time='2026-10-01T12:00:00+01:00')])
        model = build_data_relations({'water_levels': frame}, water_context())
        self.assertEqual(model['metadata']['first_observed'], '2026-10-01T12:00:00+01:00')
        self.assertEqual(model['metadata']['time_basis'], 'Offset-aware source timestamps')
        self.assertFalse(any('timezone unverified' in gap.lower() for gap in model['gaps']))

    def test_empty_response_has_requested_identity_without_fabricated_series_or_records(self):
        model = build_data_relations({}, water_context())
        self.assertEqual(model['metadata']['actual_record_count'], 0)
        self.assertEqual({node['kind'] for node in model['nodes']}, {'Source', 'Object'})
        self.assertEqual(model['edges'], [])
        self.assertTrue(any('no raw records' in gap.lower() for gap in model['gaps']))
        self.assertEqual(model['metadata']['first_observed'], '')

    def test_traffic_metrics_and_name_backfilled_mapping_are_explicitly_unverified(self):
        context = {'source': 'webtris', 'source_id': 'HS007', 'entity_id': 'traffic:6806', 'site_id': '6806',
                   'start': '2026-10-01', 'end': '2026-10-01'}
        report = pd.DataFrame([
            {'site_id': 6806.0, 'Site Name': 'A5036', 'timestamp': '2026-10-01 12:00:00', 'Total Volume': 20, 'Avg mph': 35},
            {'site_id': 6807.0, 'Site Name': 'Other', 'timestamp': '2026-10-01 12:00:00', 'Total Volume': 900, 'Avg mph': 50}])
        model = build_data_relations({'webtris_daily': report}, context)
        self.assertEqual(model['metadata']['actual_record_count'], 1)
        self.assertEqual(nodes(model, 'Source')[0]['id'], 'source:webtris_daily_a5036_api')
        self.assertEqual(nodes(model, 'Object')[0]['id'], 'traffic:6806')
        series = nodes(model, 'Series')
        self.assertEqual(len(nodes(model, 'Records')), 1)
        self.assertEqual(nodes(model, 'Records')[0]['detail']['actual_record_count'], 1)
        self.assertEqual(len([edge for edge in model['edges'] if edge['relation'] == 'returnsRecords']), 1)
        self.assertEqual({node['detail']['parameter'] for node in series}, {'Total Volume', 'Avg mph'})
        self.assertEqual({node['detail']['unit'] for node in series}, {'count/15min', 'mph'})
        linked = [edge for edge in model['edges'] if edge['relation'] in {'recordedFor', 'recordsInSeries'}]
        self.assertEqual({edge['evidence'] for edge in linked}, {'Mapping unverified'})
        self.assertTrue(all('name' in edge['evidence_ref'].lower() for edge in linked))
        self.assertIn('timezone unverified', model['metadata']['time_basis'])
        self.assertNotIn('+00:00', model['metadata']['latest_observed'])
        self.assertTrue(any('mapping' in gap.lower() for gap in model['gaps']))

    def test_absent_traffic_metric_does_not_create_a_series(self):
        context = {'source': 'webtris', 'source_id': 'HS007', 'entity_id': 'traffic:6806', 'site_id': '6806',
                   'start': '2026-10-01', 'end': '2026-10-01'}
        report = pd.DataFrame([{'site_id': '6806', 'timestamp': '2026-10-01 12:00:00', 'Total Volume': 20}])
        model = build_data_relations({'webtris_daily': report}, context)
        self.assertEqual([node['detail']['parameter'] for node in nodes(model, 'Series')], ['Total Volume'])
        self.assertTrue(any('Avg mph' in gap for gap in model['gaps']))

    def test_traffic_without_metric_fields_still_retains_raw_response(self):
        context = {'source': 'webtris', 'source_id': 'HS007', 'entity_id': 'traffic:6806', 'site_id': '6806',
                   'start': '2026-10-01', 'end': '2026-10-01'}
        report = pd.DataFrame([{'site_id': '6806', 'timestamp': '2026-10-01 12:00:00'}])
        model = build_data_relations({'webtris_daily': report}, context)
        self.assertEqual(model['metadata']['actual_record_count'], 1)
        self.assertEqual(len(nodes(model, 'Records')), 1)
        self.assertEqual(nodes(model, 'Records')[0]['detail']['actual_record_count'], 1)
        self.assertEqual(nodes(model, 'Series'), [])
        self.assertEqual([edge['relation'] for edge in model['edges']], ['returnsRecords'])
        self.assertEqual(model['edges'][0]['target'], nodes(model, 'Records')[0]['id'])
        self.assertTrue(any('Total Volume' in gap for gap in model['gaps']))
        self.assertTrue(any('Avg mph' in gap for gap in model['gaps']))

    def test_nearby_is_distance_only_retains_colocated_refs_and_excludes_bad_or_demo_points(self):
        entities = pd.DataFrame([
            {'entity_id': 'water:A', 'name': 'Gauge A', 'kind': 'Water', 'lat': 53.448, 'lon': -3.015},
            {'entity_id': 'water:B', 'name': 'Gauge B', 'kind': 'Water', 'lat': 53.448, 'lon': -3.015},
            {'entity_id': 'traffic:C', 'name': 'Counter C', 'kind': 'Traffic', 'lat': 53.449, 'lon': -3.015},
            {'entity_id': 'traffic:far', 'name': 'Far', 'kind': 'Traffic', 'lat': 54, 'lon': -3.015},
            {'entity_id': 'water:bad', 'name': 'Bad', 'kind': 'Water', 'lat': 91, 'lon': -3.015},
            {'entity_id': 'water:nan', 'name': 'NaN', 'kind': 'Water', 'lat': float('nan'), 'lon': -3.015},
            {'entity_id': 'water:inf', 'name': 'Infinity', 'kind': 'Water', 'lat': 53, 'lon': float('inf')},
            {'entity_id': 'demo:D', 'name': 'Demo', 'kind': 'Water', 'lat': 53.448, 'lon': -3.015},
            {'entity_id': 'asset:E', 'name': 'Sample', 'kind': 'Demonstration', 'lat': 53.448, 'lon': -3.015}])
        nearby = nearby_candidates(entities, 'water:A')
        self.assertEqual(nearby['Object ID'].tolist(), ['water:B', 'traffic:C'])
        self.assertEqual(nearby['Distance (km)'].iloc[0], 0)
        self.assertAlmostEqual(nearby['Distance (km)'].iloc[1], 0.111, places=3)
        self.assertTrue(nearby['Relation'].str.contains('Spatial candidate').all())
        self.assertTrue(nearby['Evidence'].str.contains('unverified', case=False).all())
        self.assertTrue(nearby['Rule'].str.contains('5').all())
        self.assertEqual(nearby_candidates(entities, 'water:A', max_km=0)['Object ID'].tolist(), ['water:B'])
        self.assertTrue(nearby_candidates(entities, 'water:bad').empty)
        self.assertTrue(nearby_candidates(entities, 'missing').empty)
        self.assertEqual(list(nearby_candidates(pd.DataFrame(), 'missing').columns),
                         ['Object', 'Object ID', 'Distance (km)', 'Relation', 'Evidence', 'Rule'])


if __name__ == '__main__':
    unittest.main()
