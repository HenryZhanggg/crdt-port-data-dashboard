"""Bounded, explicit CSV observation mapping; declarations remain provisional."""
import csv
import hashlib
import io
import json
import re

import pandas as pd

from data_integration import RECORD_COLUMNS, _number, _raw_json, _text, _time


def read_csv_upload(content):
    """Read UTF-8 CSV without inferred types, skipped rows, or silent truncation."""
    if not isinstance(content, bytes) or len(content) > 2 * 1024 * 1024:
        raise ValueError('Upload CSV bytes of at most 2 MB.')
    csv.field_size_limit(max(csv.field_size_limit(), 2 * 1024 * 1024))
    try:
        decoded = content.decode('utf-8-sig')
        if '\x00' in decoded:
            raise ValueError('CSV contains a null character.')
        reader = csv.reader(io.StringIO(decoded, newline=''), strict=True)
        header = next(reader, [])
        if not header or any(not name.strip() for name in header) or len(set(header)) != len(header):
            raise ValueError('CSV needs unique, non-empty column headings.')
        if len(header) > 100:
            raise ValueError('CSV may contain at most 100 columns.')
        rows, row_numbers = [], []
        previous_line = reader.line_num
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f'CSV row {previous_line + 1} has {len(row)} fields; expected {len(header)}.')
            rows.append(row)
            row_numbers.append(previous_line + 1)
            previous_line = reader.line_num
            if len(rows) > 10000:
                raise ValueError('CSV may contain at most 10,000 data rows; no rows were imported.')
        if not rows:
            raise ValueError('CSV has no data rows.')
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError('CSV must be valid UTF-8 with correctly quoted, comma-separated fields: ' + str(error)) from error
    frame = pd.DataFrame(rows, columns=header)
    frame.attrs.update(content_sha256=hashlib.sha256(content).hexdigest(), csv_row_numbers=row_numbers)
    return frame


def map_tabular_observations(frame, mapping, metadata, collected_at):
    """Keep every row and its evidence; invalid data is flagged for snapshot exclusion."""
    for field in ['entity_id', 'value', 'event_time']:
        if not mapping.get(field):
            raise ValueError('Choose a CSV column for ' + field + '.')
    for field, column in mapping.items():
        if column and column not in frame:
            raise ValueError('Unknown CSV column for ' + field + ': ' + str(column))
    kind = metadata.get('kind', 'generic')
    assumption = metadata.get('event_timezone')
    if kind not in {'generic', 'water_level'} or assumption not in (None, 'UTC', 'Europe/London'):
        raise ValueError('Choose a supported observation kind and time assumption.')
    required = ['metric', 'unit'] + (['datum_uri', 'qualifier'] if kind == 'water_level' else [])
    for field in required:
        if not mapping.get(field) and not _text(metadata.get(field)):
            raise ValueError('Declare ' + field + ' using a CSV column or a constant.')
    collected = _time(collected_at)
    if pd.isna(collected):
        raise ValueError('Upload collection time must be timezone-aware.')
    file_hash = frame.attrs.get('content_sha256')
    if not file_hash:
        raise ValueError('Read the original CSV upload before mapping it.')
    source_id, output = 'CSV:' + file_hash, []
    for position, raw in enumerate(frame.to_dict('records')):
        def declared(field):
            return _text(raw.get(mapping[field])) if mapping.get(field) else _text(metadata.get(field))
        identity, metric, unit = (declared(field) for field in ['entity_id', 'metric', 'unit'])
        datum, qualifier, concept = (declared(field) for field in ['datum_uri', 'qualifier', 'concept_uri'])
        flags = ['provisional_identity', 'unverified_concept_mapping']
        for field, value in [('entity', identity), ('metric', metric), ('unit', unit),
                             *([('datum', datum), ('qualifier', qualifier)] if kind == 'water_level' else [])]:
            if not value:
                flags.append('missing_' + field)
        value = _number(raw.get(mapping['value']))
        if pd.isna(value):
            flags.append('invalid_value')
        source_time = _text(raw.get(mapping['event_time']))
        event, basis = pd.NaT, 'Invalid CSV timestamp format'
        if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}'
                        r'(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-][0-9]{2}(?::?[0-9]{2})?)?', source_time):
            event, basis = _time(source_time), 'Offset-aware CSV timestamp'
            if pd.isna(event):
                event = _time(source_time, assumption)
                basis = 'User-assumed ' + assumption + ' (unverified)' if assumption else 'CSV timezone unverified'
                flags.append('assumed_timezone' if assumption else 'unverified_timezone')
        if pd.isna(event):
            flags.append('invalid_event_time')
        parts = [source_id, identity, metric, unit, datum, qualifier, concept]
        series = 'csv:series:' + hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:20]
        evidence = {'csv_row_number': frame.attrs['csv_row_numbers'][position],
                    'record': json.loads(_raw_json(raw)), 'declared_concept_uri': concept}
        output.append(dict(zip(RECORD_COLUMNS, [source_id, 'csv_upload', 'csv:' + (identity or 'unknown'),
            series, metric, value, unit, datum, metric if kind == 'water_level' else '', qualifier,
            '', '', 'upload:sha256:' + file_hash, source_time, event, collected,
            'Dashboard upload (not original historical arrival)', basis, '; '.join(flags),
            json.dumps(evidence, sort_keys=True, allow_nan=False)])))
    result = pd.DataFrame(output, columns=RECORD_COLUMNS)
    for column in ['event_time', 'available_at']:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result
