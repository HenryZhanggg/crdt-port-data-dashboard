"""Small, source-derived relation views over selected raw observation responses."""
from __future__ import annotations

from hashlib import sha256
import json
import math

import pandas as pd

from workspace_links import filter_context_bundle


NEARBY_COLUMNS = ['Object', 'Object ID', 'Distance (km)', 'Relation', 'Evidence', 'Rule']
WATER_IDENTITY = ['station_reference', 'parameter', 'qualifier', 'unit', 'datum_uri', 'measure_uri']
TRAFFIC_MAPPING = ('Report site_id is backfilled by matching Site Name to the sites description; '
                   'the report-to-counter mapping is not source-confirmed.')


def _text(value):
    if value is None or pd.isna(value):
        return ''
    return value.isoformat() if isinstance(value, pd.Timestamp) else str(value)


def _canonical(value):
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or pd.isna(value):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _json(value):
    return json.dumps(_canonical(value), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _identifier(kind, value):
    return kind + ':' + sha256(_json(value).encode('utf-8')).hexdigest()[:24]


def _values(frame, field):
    return '; '.join(sorted({_text(value) for value in frame.get(field, []) if _text(value)}))


def _times(frame, column):
    valid = []
    unverified = False
    nonzero_offset = False
    for value in frame.get(column, []):
        time = pd.to_datetime(value, errors='coerce')
        if pd.isna(time):
            continue
        unverified |= time.tzinfo is None
        nonzero_offset |= time.tzinfo is not None and time.utcoffset().total_seconds() != 0
        order = time.tz_localize('UTC') if time.tzinfo is None else time.tz_convert('UTC')
        valid.append((order, _text(value)))
    valid.sort()
    basis = 'source timezone unverified' if unverified or not valid else (
        'Offset-aware source timestamps' if nonzero_offset else 'UTC')
    return valid[0][1] if valid else '', valid[-1][1] if valid else '', basis


def _conflicts(rows, time_column, value_columns):
    timestamps = {}
    for row in rows:
        stamp = _text(row.get(time_column))
        if stamp:
            timestamps.setdefault(stamp, set()).add(_json([row.get(field) for field in value_columns]))
    return sum(len(values) > 1 for values in timestamps.values())


def build_data_relations(bundle, context):
    """Describe exact selected raw rows without asserting canonical asset identity."""
    selected = filter_context_bundle(bundle, context)
    water = context['source'] == 'water_level'
    connector = 'ea_liverpool_tide_water_level_api' if water else 'webtris_daily_a5036_api'
    table, time_column = ('water_levels', 'date_time') if water else ('webtris_daily', 'timestamp')
    frame = selected.get(table, pd.DataFrame())
    status = selected.get('status', pd.DataFrame())
    if 'connector_id' in status:
        status = status.loc[status['connector_id'].eq(connector)]
    else:
        status = pd.DataFrame()
    endpoint = _values(frame, 'api_endpoint') or _values(status, 'api_endpoint')
    checked = _values(status, 'last_call_utc') or _values(frame, 'retrieved_at_utc')
    first, latest, time_basis = _times(frame, time_column)
    reference = {field: _text(context.get(field)) for field in
                 (['station_reference', 'unit', 'datum_uri'] if water else ['site_id'])}
    identity_note = ('Provisional workspace identity derived from source references; '
                     'not an authoritative cross-system asset ID. '
                     'Series retain exact source property, qualifier, unit, datum and available measure URI.')
    if not water:
        identity_note += ' ' + TRAFFIC_MAPPING
    metadata = {'selected_object': context['entity_id'], 'source': connector,
                'source_endpoint': endpoint, 'checked_at': checked, 'actual_record_count': len(frame),
                'reference': reference, 'time_basis': time_basis,
                'requested_start': _text(context.get('start')), 'requested_end': _text(context.get('end')),
                'first_observed': first, 'latest_observed': latest, 'identity_note': identity_note}
    source_id = 'source:' + connector
    object_id = context['entity_id']
    model = {'nodes': [
        {'id': source_id, 'label': 'EA Liverpool tide readings' if water else 'WebTRIS traffic report',
         'kind': 'Source', 'evidence': 'Source product',
         'detail': {'connector_id': connector, 'catalogue_id': context.get('source_id', ''),
                    'source_endpoint': endpoint, 'checked_at': checked}},
        {'id': object_id, 'label': ('Water gauge ' + reference['station_reference']) if water else
         ('Traffic counter ' + reference['site_id']), 'kind': 'Object',
         'evidence': 'Source-derived reference' if water else 'Mapping unverified',
         'detail': dict(reference, identity_note=identity_note, station_uri=_values(frame, 'station_uri'))}],
        'edges': [], 'metadata': metadata, 'gaps': []}
    gaps = model['gaps']
    if not endpoint:
        gaps.append('Source endpoint was not supplied with the selected response.')
    if not checked:
        gaps.append('Source check time was not supplied; no check time has been inferred.')
    if not water:
        gaps.append('Mapping unverified: ' + TRAFFIC_MAPPING)
    if 'unverified' in time_basis and not frame.empty:
        gaps.append('Source timezone unverified; source timestamps have not been labelled UTC.')
    if frame.empty:
        gaps.append('No raw records returned for the requested object, reference and date window.')
        return model

    groups = {}
    if water:
        for row in frame.to_dict('records'):
            identity = {field: _text(row.get(field)) for field in WATER_IDENTITY}
            groups.setdefault(_json(identity), (identity, []))[1].append(row)
    else:
        for metric, unit in [('Total Volume', 'count/15min'), ('Avg mph', 'mph')]:
            if metric not in frame:
                gaps.append('No ' + metric + ' field returned; no series has been created for this metric.')
                continue
            identity = {'site_id': reference['site_id'], 'parameter': metric, 'unit': unit}
            groups[_json(identity)] = (identity, frame.to_dict('records'))

    record_ids = set()
    for key in sorted(groups):
        identity, rows = groups[key]
        series_id = _identifier('series', [connector, identity])
        raw_rows = sorted(_json(row) for row in rows)
        records_id = _identifier('records', [connector, series_id, raw_rows] if water else [connector, raw_rows])
        group = pd.DataFrame(rows)
        group_first, group_latest, _ = _times(group, time_column)
        value_column = 'value' if water else identity['parameter']
        conflicts = _conflicts(rows, time_column, [value_column])
        if conflicts:
            gaps.append(f'{conflicts} timestamp(s) contain conflicting raw values; all returned rows are retained.')
        if water:
            missing = [field for field in WATER_IDENTITY[:-1] if not identity[field]]
            if missing:
                gaps.append('Unverified series identity fields: ' + ', '.join(missing) + '; no values inferred.')
            if not identity['measure_uri']:
                gaps.append('Source measure_uri not supplied; series identity uses the provisional source tuple.')
        series_label = ((identity['parameter'] or 'Unknown property') + ' · ' +
                        (identity.get('qualifier', '') + ' · ' if water else '') +
                        (identity['unit'] or 'Unknown unit'))
        evidence = 'Source-derived' if water else 'Mapping unverified'
        evidence_ref = (identity.get('measure_uri') or _json(identity)) if water else TRAFFIC_MAPPING
        model['nodes'].append(
            {'id': series_id, 'label': series_label, 'kind': 'Series', 'evidence': evidence,
             'detail': dict(identity, actual_record_count=len(rows), conflicting_timestamp_count=conflicts)})
        if records_id not in record_ids:
            record_ids.add(records_id)
            record_conflicts = conflicts if water else _conflicts(rows, time_column, ['Total Volume', 'Avg mph'])
            model['nodes'].append(
                {'id': records_id, 'label': f'{len(rows)} raw records', 'kind': 'Records', 'evidence': evidence,
                 'detail': {'actual_record_count': len(rows), 'exact_duplicate_count': len(rows) - len(set(raw_rows)),
                            'conflicting_timestamp_count': record_conflicts, 'first_observed': group_first,
                            'latest_observed': group_latest, 'source_endpoint': _values(group, 'api_endpoint') or endpoint,
                            'reading_sources': _values(group, 'reading_source') or _values(group, 'reading_uri')}})
            model['edges'].append(
                {'source': source_id, 'target': records_id, 'relation': 'returnsRecords',
                 'evidence': 'Source response', 'evidence_ref': endpoint or connector})
        model['edges'].extend([
            {'source': records_id, 'target': series_id, 'relation': 'recordsInSeries',
             'evidence': evidence, 'evidence_ref': evidence_ref},
            {'source': series_id, 'target': object_id, 'relation': 'recordedFor',
             'evidence': evidence, 'evidence_ref': evidence_ref}])
    if not water and not groups:
        raw_rows = sorted(_json(row) for row in frame.to_dict('records'))
        records_id = _identifier('records', [connector, raw_rows])
        model['nodes'].append(
            {'id': records_id, 'label': f'{len(frame)} raw records', 'kind': 'Records', 'evidence': 'Mapping unverified',
             'detail': {'actual_record_count': len(frame), 'exact_duplicate_count': len(frame) - len(set(raw_rows)),
                        'first_observed': first, 'latest_observed': latest, 'source_endpoint': endpoint,
                        'reading_sources': _values(frame, 'reading_source') or _values(frame, 'reading_uri')}})
        model['edges'].append(
            {'source': source_id, 'target': records_id, 'relation': 'returnsRecords',
             'evidence': 'Source response', 'evidence_ref': endpoint or connector})
    model['gaps'] = sorted(set(gaps))
    return model


def nearby_candidates(entities, selected_id, max_km=5):
    """Return distance candidates, never a verified operational dependency."""
    result = pd.DataFrame(columns=NEARBY_COLUMNS)
    if entities.empty or 'entity_id' not in entities:
        return result
    frame = entities.copy()
    for field, limit in [('lat', 90), ('lon', 180)]:
        frame[field] = pd.to_numeric(frame.get(field, pd.Series(index=frame.index, dtype=float)), errors='coerce')
        frame = frame.loc[frame[field].between(-limit, limit)]
    ids = frame['entity_id'].fillna('').astype(str)
    kinds = frame.get('kind', pd.Series('', index=frame.index)).fillna('').astype(str).str.lower()
    frame = frame.loc[~ids.str.startswith('demo:') & ~kinds.isin(['demonstration', 'demo', 'sample', 'illustrative'])]
    selected = frame.loc[frame['entity_id'].eq(selected_id)]
    if selected.empty:
        return result
    origin = selected.iloc[0]
    rows = []
    for _, row in frame.loc[~frame['entity_id'].eq(selected_id)].iterrows():
        lat1, lat2 = math.radians(origin['lat']), math.radians(row['lat'])
        delta_lat = lat2 - lat1
        delta_lon = math.radians(row['lon'] - origin['lon'])
        haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        distance = 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, haversine))))
        if distance <= max_km:
            rows.append({'Object': _text(row.get('name')) or str(row['entity_id']), 'Object ID': row['entity_id'],
                         'Distance (km)': round(distance, 3), 'Relation': 'Spatial candidate',
                         'Evidence': 'Business dependency unverified',
                         'Rule': f'Haversine distance ≤ {max_km:g} km; proximity only'})
    return pd.DataFrame(rows, columns=NEARBY_COLUMNS).sort_values(['Distance (km)', 'Object ID']).reset_index(drop=True)
