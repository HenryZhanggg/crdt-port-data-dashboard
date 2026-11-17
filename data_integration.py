"""Inspectable observation alignment and explicitly simulated availability replay."""
from __future__ import annotations

import hashlib
import io
import json
import math
import numbers
import re
import zipfile

import pandas as pd


RECORD_COLUMNS = ['source_id', 'source', 'entity_id', 'series_id', 'metric', 'value', 'unit',
                  'datum_uri', 'parameter', 'qualifier', 'measure_uri', 'reading_uri', 'source_uri',
                  'source_time', 'event_time', 'available_at', 'availability_basis', 'time_basis',
                  'quality_flags', 'raw_record']
SNAPSHOT_COLUMNS = RECORD_COLUMNS + ['status', 'age_minutes', 'last_value', 'cutoff', 'record_count']
AUDIT_COLUMNS = RECORD_COLUMNS + ['effective_available_at', 'included', 'exclusion_reason', 'selected']
BLOCKING_FLAGS = {'invalid_value', 'invalid_event_time', 'unverified_timezone', 'missing_entity',
                  'missing_unit', 'missing_metric', 'missing_datum', 'missing_qualifier'}


def _text(value):
    return '' if value is None or pd.isna(value) else str(value).strip()


def _time(value, assumption=None):
    try:
        result = pd.Timestamp(value)
        if pd.isna(result):
            return pd.NaT
        if result.tzinfo is None:
            if not assumption:
                return pd.NaT
            result = result.tz_localize(assumption, ambiguous='NaT', nonexistent='NaT')
        return result.tz_convert('UTC') if pd.notna(result) else pd.NaT
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def _number(value):
    if isinstance(value, bool) or type(value).__name__ == 'bool_':
        return float('nan')
    try:
        result = float(value)
        return result if math.isfinite(result) else float('nan')
    except (ValueError, TypeError, OverflowError):
        return float('nan')


def _raw_json(row):
    clean = {}
    for name, value in row.items():
        if value is None or pd.isna(value):
            clean[name] = None
        elif isinstance(value, numbers.Real) and not math.isfinite(value):
            clean[name] = str(value)
        else:
            clean[name] = value
    return json.dumps(clean, sort_keys=True, default=str, allow_nan=False)


def _collection_time(row, status, connector):
    value = row.get('retrieved_at_utc')
    if not _text(value) and not status.empty and 'connector_id' in status:
        matching = status.loc[status['connector_id'].eq(connector)]
        if not matching.empty:
            value = matching.iloc[-1].get('last_call_utc')
    return _time(value)


def normalise_observations(bundle, traffic_timezone=None):
    """Keep source references separate; local collection time is not publication time."""
    if traffic_timezone not in (None, 'UTC', 'Europe/London'):
        raise ValueError('Choose no traffic assumption, UTC, or Europe/London.')
    output = []
    status = bundle.get('status', pd.DataFrame())
    definitions = [
        ('water_levels', 'HS004', 'water_level', 'water', 'station_reference', 'date_time',
         'ea_liverpool_tide_water_level_api', [('value', None)]),
        ('webtris_daily', 'HS007', 'webtris', 'traffic', 'site_id', 'timestamp',
         'webtris_daily_a5036_api', [('Total Volume', 'vehicles / 15 min'), ('Avg mph', 'mph')]),
    ]
    for table, source_id, source, prefix, id_field, time_field, connector, metrics in definitions:
        frame = bundle.get(table, pd.DataFrame())
        for raw in frame.to_dict('records'):
            for value_field, fixed_unit in metrics:
                if value_field not in raw:
                    continue
                flags = []
                identity = _text(raw.get(id_field))
                if source == 'webtris':
                    identity = re.sub(r'\.0+$', '', identity)
                metric = _text(raw.get('parameter')) if source == 'water_level' else value_field
                unit = _text(raw.get('unit')) if fixed_unit is None else fixed_unit
                datum = _text(raw.get('datum_uri')) if source == 'water_level' else ''
                qualifier = _text(raw.get('qualifier')) if source == 'water_level' else ''
                measure = _text(raw.get('measure_uri'))
                for missing, flag in [(not identity, 'missing_entity'), (not metric, 'missing_metric'),
                                      (not unit, 'missing_unit'),
                                      (source == 'water_level' and not datum, 'missing_datum'),
                                      (source == 'water_level' and not qualifier, 'missing_qualifier')]:
                    if missing:
                        flags.append(flag)
                value = _number(raw.get(value_field))
                if pd.isna(value):
                    flags.append('invalid_value')
                event = _time(raw.get(time_field))
                basis = 'Offset-aware source timestamp'
                if pd.isna(event):
                    if source == 'webtris' and traffic_timezone:
                        event = _time(raw.get(time_field), traffic_timezone)
                        basis = 'User-assumed ' + traffic_timezone + ' (unverified)'
                        flags.append('assumed_timezone')
                    elif source == 'webtris':
                        basis = 'Source timezone unverified'
                        flags.append('unverified_timezone')
                    else:
                        basis = 'Invalid or timezone-unverified source timestamp'
                if pd.isna(event):
                    flags.append('invalid_event_time')
                available = _collection_time(raw, status, connector)
                if pd.isna(available):
                    flags.append('unknown_availability')
                parts = [source_id, identity, metric, unit, datum, qualifier, measure]
                series_id = prefix + ':series:' + hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:20]
                reading = _text(raw.get('reading_uri'))
                source_uri = reading or measure or _text(raw.get('api_endpoint'))
                if not source_uri and not status.empty and 'connector_id' in status:
                    matching = status.loc[status['connector_id'].eq(connector)]
                    if not matching.empty:
                        source_uri = _text(matching.iloc[-1].get('api_endpoint'))
                output.append(dict(zip(RECORD_COLUMNS, [source_id, source, prefix + ':' + (identity or 'unknown'),
                    series_id, metric, value, unit, datum, metric if source == 'water_level' else '', qualifier,
                    measure, reading, source_uri, _text(raw.get(time_field)), event, available,
                    'Dashboard retrieval (not provider publication)' if pd.notna(available) else 'Unknown collection time',
                    basis, '; '.join(flags), _raw_json(raw)])))
    result = pd.DataFrame(output, columns=RECORD_COLUMNS)
    for column in ['event_time', 'available_at']:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


def integration_snapshot(records, cutoff, freshness_minutes=60, availability_mode='retrieval',
                         delay_minutes=0, drop_every=0):
    """Return latest usable values and all exclusion evidence at an aware cut-off."""
    point = _time(cutoff)
    if pd.isna(point):
        raise ValueError('The cut-off must be a valid timezone-aware timestamp.')
    for name, value, positive in [('freshness_minutes', freshness_minutes, True), ('delay_minutes', delay_minutes, False)]:
        if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
            raise ValueError(name + ' is outside the allowed range.')
    if isinstance(drop_every, bool) or not isinstance(drop_every, numbers.Integral) or drop_every < 0:
        raise ValueError('drop_every must be a non-negative integer.')
    if availability_mode not in {'retrieval', 'replay'}:
        raise ValueError('Use retrieval or replay availability mode.')
    if not set(RECORD_COLUMNS).issubset(records.columns):
        raise ValueError('Use normalise_observations before creating a snapshot.')
    audit = records.copy(deep=True).reset_index(drop=True)
    audit['effective_available_at'] = audit['available_at']
    if availability_mode == 'replay':
        audit['effective_available_at'] = audit['event_time'] + pd.Timedelta(minutes=delay_minutes)
        audit['availability_basis'] = 'Simulated event time + delay; not measured provider latency'
    audit['included'] = False
    audit['exclusion_reason'] = ''
    audit['selected'] = False
    if audit.empty:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS), audit.reindex(columns=AUDIT_COLUMNS)
    invalid = audit['quality_flags'].map(lambda flags: bool(set(str(flags).split('; ')) & BLOCKING_FLAGS))
    dropped = pd.Series(False, index=audit.index)
    if availability_mode == 'replay' and drop_every:
        ordered = audit.sort_values(['event_time', 'series_id', 'raw_record'], kind='stable', na_position='last').index
        dropped.loc[ordered[drop_every - 1::drop_every]] = True
    for index, row in audit.iterrows():
        if invalid.loc[index]:
            reason = 'Invalid: ' + row['quality_flags']
        elif row['event_time'] > point:
            reason = 'Future event at cut-off'
        elif dropped.loc[index]:
            reason = 'Simulated missing record'
        elif pd.isna(row['effective_available_at']):
            reason = 'Unknown availability time'
        elif row['effective_available_at'] > point:
            reason = 'Not yet available at cut-off'
        else:
            reason = ''
        audit.at[index, 'exclusion_reason'] = reason
        audit.at[index, 'included'] = not bool(reason)
    eligible = audit.loc[audit['included']]
    duplicates = eligible.index[eligible.duplicated(['series_id', 'event_time', 'value', 'available_at', 'source_uri'])]
    audit.loc[duplicates, 'included'] = False
    audit.loc[duplicates, 'exclusion_reason'] = 'Exact duplicate'
    snapshots = []
    for _, group in audit.groupby('series_id', sort=True, dropna=False):
        candidate = group.loc[group['included']]
        output = group.iloc[0].reindex(RECORD_COLUMNS).to_dict()
        output.update(status='Invalid' if invalid.loc[group.index].all() else 'Unknown', value=float('nan'),
                      last_value=float('nan'), event_time=pd.NaT, available_at=pd.NaT,
                      age_minutes=None, cutoff=point, record_count=len(group))
        if not candidate.empty:
            latest_time = candidate['event_time'].max()
            latest = candidate.loc[candidate['event_time'].eq(latest_time)]
            chosen = latest.iloc[0]
            output.update(chosen.reindex(RECORD_COLUMNS).to_dict())
            output['available_at'] = chosen['effective_available_at']
            output['age_minutes'] = (point - latest_time).total_seconds() / 60
            output['value'] = float('nan')
            if latest['value'].nunique() > 1:
                output['status'] = 'Conflict'
                audit.loc[latest.index, 'exclusion_reason'] = 'Conflicting latest values'
            else:
                output['last_value'] = chosen['value']
                if output['age_minutes'] > freshness_minutes:
                    output['status'] = 'Stale'
                    audit.loc[latest.index, 'exclusion_reason'] = 'Stale at cut-off'
                else:
                    output['status'] = 'Available under time assumption' if 'assumed_timezone' in chosen['quality_flags'] else 'Available'
                    output['value'] = chosen['value']
                    audit.at[chosen.name, 'selected'] = True
            older = candidate.index[candidate['event_time'].lt(latest_time)]
            audit.loc[older, 'exclusion_reason'] = 'Earlier eligible observation'
        snapshots.append(output)
    return pd.DataFrame(snapshots, columns=SNAPSHOT_COLUMNS), audit.reindex(columns=AUDIT_COLUMNS)


def integration_archive(records, snapshot, audit, rules):
    """Export all inputs, decisions and explicit evidence boundaries without execution."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for filename, frame in [('observations.csv', records), ('snapshot.csv', snapshot), ('audit.csv', audit)]:
            archive.writestr(filename, frame.to_csv(index=False))
        archive.writestr('rules.json', json.dumps(rules, indent=2, default=str, allow_nan=False))
        archive.writestr('README.txt',
            'CRDT observation integration workbench export\n'
            'Dashboard retrieval is a local collection timestamp, not provider publication or original historical availability.\n'
            'Replay availability and dropped records are simulated assumptions, not measured operational latency.\n'
            'Source-derived identities and concept mappings remain provisional; no formal WP1 approval is implied.\n'
            'Available means the configured data checks passed; model suitability, physical accuracy and safety require separate validation.\n'
            'Missing, stale, conflicting and invalid outputs retain missing values. Units and datums are never converted.\n')
    return buffer.getvalue()
