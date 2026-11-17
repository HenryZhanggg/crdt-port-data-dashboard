"""Bind explicit feature requirements to one observation decision cut-off."""
import keyword
import re

import pandas as pd

from data_integration import SNAPSHOT_COLUMNS, _number, _time


def build_model_inputs(snapshot, requirements, allow_time_assumptions=False):
    """Return a one-row feature table and checks; unavailable values remain missing."""
    if not isinstance(allow_time_assumptions, bool):
        raise ValueError('allow_time_assumptions must be explicitly True or False.')
    fields = ['input_name', 'series_id', 'expected_unit', 'required']
    requirements = pd.DataFrame(requirements).copy()
    if not set(fields).issubset(requirements.columns):
        raise ValueError('Requirements need input_name, series_id, expected_unit and required.')
    names = requirements['input_name'].tolist()
    reserved = set(SNAPSHOT_COLUMNS + fields + ['passed', 'check', 'concept_ref'])
    if any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name)
           or keyword.iskeyword(name) or name in reserved for name in names) or len(set(names)) != len(names):
        raise ValueError('Each input_name must be a unique, safe name and cannot replace metadata.')
    if requirements['required'].map(lambda value: type(value).__name__ not in {'bool', 'bool_'}).any():
        raise ValueError('Each required flag must be explicitly True or False.')
    if requirements['series_id'].map(lambda value: not isinstance(value, str) or not value.strip()).any():
        raise ValueError('Each requirement must bind an explicit series_id.')
    if 'series_id' not in snapshot or snapshot['series_id'].duplicated().any():
        raise ValueError('Snapshot must have unique series_id rows; aggregation is not supported.')
    cutoff = pd.NaT
    if not snapshot.empty:
        points = snapshot.get('cutoff', pd.Series(index=snapshot.index, dtype=object)).map(_time)
        if points.isna().any() or points.nunique() != 1:
            raise ValueError('Snapshot rows must share one valid timezone-aware cut-off.')
        cutoff = points.iloc[0]
    row, checks = {'cutoff': cutoff}, []
    indexed = snapshot.set_index('series_id', drop=False)
    for requirement in requirements.to_dict('records'):
        series_id = requirement['series_id']
        source = indexed.loc[series_id].to_dict() if series_id in indexed.index else {}
        unit = source.get('unit', '')
        expected = requirement['expected_unit']
        status = source.get('status', 'Missing')
        value = _number(source.get('value'))
        if not source:
            reason = 'Missing series'
        elif status == 'Available under time assumption' and not allow_time_assumptions:
            reason = 'Time assumption requires explicit permission'
        elif status not in {'Available', 'Available under time assumption'}:
            reason = str(status) + ' at cut-off'
        elif not isinstance(expected, str) or not expected.strip():
            reason = 'Expected unit is missing'
        elif unit != expected:
            reason = 'Unit mismatch; no conversion applied'
        elif pd.isna(value):
            reason = 'Invalid numeric value'
        else:
            reason = 'Configured checks passed' + (' under time assumption' if status.endswith('assumption') else '')
        passed = reason.startswith('Configured checks passed')
        row[requirement['input_name']] = value if passed else float('nan')
        check = {**source, **{field: requirement[field] for field in fields},
                 'cutoff': cutoff, 'status': status, 'passed': passed, 'check': reason}
        if 'concept_ref' in requirement:
            check['concept_ref'] = requirement['concept_ref']
        checks.append(check)
    columns = list(dict.fromkeys(fields + ['passed', 'check'] + list(snapshot.columns) + ['concept_ref']))
    return pd.DataFrame([row]), pd.DataFrame(checks).reindex(columns=columns)
