"""Explicit, reversible declarations for combining equivalent source series."""
import hashlib
import json

import pandas as pd


BINDING_COLUMNS = ['source_id','series_id','source_entity_id','source_metric','unit',
                   'datum_uri','qualifier','common_entity_id','common_concept','confirmed']
LINKAGE_COLUMNS = BINDING_COLUMNS + ['joint_series_id','group_series_count','group_source_count','status','reason']
_DESCRIPTORS = {'source_entity_id':'entity_id','source_metric':'metric','unit':'unit',
                'datum_uri':'datum_uri','qualifier':'qualifier'}
_PROFILE_VERSION = '2026-11-19.1'


def _text(value):
    return '' if value is None or pd.isna(value) else str(value).strip()


def _source_text(value):
    return str(value) if _text(value) else ''


def integration_bindings(records):
    """Return one unconfirmed declaration per source/series, in stable order."""
    records = pd.DataFrame(records)
    if records.empty:
        return pd.DataFrame(columns=BINDING_COLUMNS).astype({'confirmed':bool})
    missing = {'source_id','series_id',*_DESCRIPTORS.values()}.difference(records.columns)
    if missing:
        raise ValueError('Records are missing columns: '+', '.join(sorted(missing)))
    series = {}
    for record in records.to_dict('records'):
        key = (_text(record['source_id']),_text(record['series_id']))
        if not all(key):
            raise ValueError('Every record needs a nonblank source_id and series_id')
        description = {name:_source_text(record[column]) for name,column in _DESCRIPTORS.items()}
        if key in series and series[key] != description:
            raise ValueError('Ambiguous source metadata for series: '+repr(key))
        series[key] = description
    return pd.DataFrame([{'source_id':key[0],'series_id':key[1],**series[key],
        'common_entity_id':'','common_concept':'','confirmed':False} for key in sorted(series)],columns=BINDING_COLUMNS)


def apply_integration_bindings(records,bindings):
    """Map confirmed declarations; preserve units, clocks, flags and original evidence."""
    mapped = pd.DataFrame(records).copy(deep=True)
    rows = integration_bindings(mapped).to_dict('records')
    known = {(row['source_id'],row['series_id']):row for row in rows}
    bindings = pd.DataFrame(bindings)
    if not bindings.empty:
        missing = {'source_id','series_id','common_entity_id','common_concept','confirmed'}.difference(bindings.columns)
        if missing:
            raise ValueError('Bindings are missing columns: '+', '.join(sorted(missing)))
    seen = set()
    for binding in bindings.to_dict('records'):
        key = (_text(binding['source_id']),_text(binding['series_id']))
        if key in seen:
            raise ValueError('Duplicate binding for series: '+repr(key))
        seen.add(key)
        if key not in known:
            raise ValueError('Binding refers to an unknown series: '+repr(key))
        if type(binding['confirmed']) is not bool:
            raise ValueError('Binding confirmed must be a boolean')
        row = known[key]
        for field in _DESCRIPTORS:
            if field in binding and _source_text(binding[field]) != row[field]:
                raise ValueError('Binding source metadata differs from records: '+field)
        row.update(common_entity_id=_text(binding['common_entity_id']),
                   common_concept=_text(binding['common_concept']),confirmed=binding['confirmed'])
    groups,dimensions = {},{}
    for row in rows:
        if row['confirmed'] and row['common_entity_id'] and row['common_concept']:
            meaning = (row['common_entity_id'],row['common_concept'])
            dimension = (row['unit'],row['datum_uri'],row['qualifier'])
            groups.setdefault(meaning+dimension,[]).append(row)
            dimensions.setdefault(meaning,set()).add(dimension)
    assignments = {}
    for group,members in groups.items():
        encoded = json.dumps(group,ensure_ascii=False,separators=(',',':'))
        joint_id = 'joint:'+hashlib.sha256(encoded.encode()).hexdigest()
        source_count = len({row['source_id'] for row in members})
        variants = dimensions[group[:2]]
        differing = [name for index,name in enumerate(('unit','datum_uri','qualifier'))
                     if len({variant[index] for variant in variants}) > 1]
        for row in members:
            row.update(joint_series_id=joint_id,group_series_count=len(members),group_source_count=source_count,
                status='incompatible' if differing else 'mapped',
                reason='Different '+', '.join(differing)+'; kept in separate groups.' if differing
                       else 'Confirmed mapping across %d source(s).'%source_count)
            assignments[(row['source_id'],row['series_id'])] = row
    for row in rows:
        if 'status' not in row:
            row.update(joint_series_id='',group_series_count=0,group_source_count=0,status='unmatched',
                reason='Mapping is not confirmed.' if not row['confirmed']
                       else 'Confirmed mapping needs a common entity and concept.')
    if not mapped.empty:
        originals = mapped.to_dict('records')
        for field,original in [('source_entity_id','entity_id'),('source_series_id','series_id'),('source_metric','metric')]:
            mapped[field] = [record[original] for record in originals]
        for position,original in enumerate(originals):
            declaration = assignments.get((_text(original['source_id']),_text(original['series_id'])))
            if declaration is None:
                continue
            for field,value in [('entity_id',declaration['common_entity_id']),('metric',declaration['common_concept']),
                                ('series_id',declaration['joint_series_id'])]:
                mapped.iat[position,mapped.columns.get_loc(field)] = value
            evidence = {'integration_product':{'profile_version':_PROFILE_VERSION,'source_id':original['source_id'],
                'source_entity_id':original['entity_id'],'source_series_id':original['series_id'],
                'source_metric':original['metric'],'common_entity_id':declaration['common_entity_id'],
                'common_concept':declaration['common_concept']},'original_raw_record':original.get('raw_record')}
            mapped.iat[position,mapped.columns.get_loc('raw_record')] = json.dumps(evidence,ensure_ascii=False,sort_keys=True,default=str)
    return mapped,pd.DataFrame(rows,columns=LINKAGE_COLUMNS)
