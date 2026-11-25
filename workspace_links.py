"""Explicit observation context for the Overview, Monitor and Data pages."""
import pandas as pd
import streamlit as st

from data_quality import filter_dates


def water_handoff_context(series):
    if not series:
        return None
    station = str(series.get('station_reference') or '')
    if not station:
        identifier = str(series.get('id', ''))
        parts = identifier[6:].split('|', 2) if identifier.startswith('water:') else []
        if len(parts) != 3 or parts[1] != str(series.get('unit', '')) or parts[2] != str(series.get('datum_uri', '')):
            return None
        station = parts[0]
    unit = str(series.get('unit') or '')
    if not station or not unit or series.get('datum_uri') is None:
        return None
    times = pd.to_datetime([row.get('time') for row in series.get('rows', [])], utc=True, errors='coerce', format='mixed')
    times = times.dropna()
    times = times[times <= pd.Timestamp.now(tz='UTC')]
    if times.empty:
        return None
    end = times.max().date()
    start = max(times.min().date(), (pd.Timestamp(end) - pd.Timedelta(days=6)).date())
    context = {'source': 'water_level', 'source_id': 'HS004', 'entity_id': 'water:' + station,
        'station_reference': station, 'unit': unit, 'datum_uri': str(series['datum_uri']),
        'start': start.isoformat(), 'end': end.isoformat()}
    measure = series.get('measure_uri')
    if isinstance(measure, str) and measure:
        context['measure_uri'] = measure
    return context


def reference_key(context):
    return '|'.join(context[field] for field in ['station_reference', 'unit', 'datum_uri'])


def context_label(context):
    identity = reference_key(context) if context['source'] == 'water_level' else 'Traffic counter ' + context['site_id']
    if context.get('measure_uri'):
        identity += ' · Measure ' + context['measure_uri'].rstrip('/').rsplit('/', 1)[-1]
    basis = 'UTC' if context['source'] == 'water_level' else 'source timezone unverified'
    return f"{identity} · {context['start']} to {context['end']} · {basis}"


def context_allowed(context, views):
    permission = 'weather' if context['source'] == 'water_level' else 'transport'
    return permission in views


def open_water_observations(series):
    context = water_handoff_context(series)
    if context is None:
        return
    st.session_state['monitor_handoff'] = context
    st.session_state['dashboard_page'] = 'Monitor'
    st.session_state['monitor_data_mode'] = 'Connected observations'
    st.session_state['monitor_mode'] = 'Historical browsing'
    st.session_state['monitor_dates_Historical browsing'] = tuple(pd.Timestamp(context[key]).date() for key in ['start', 'end'])
    st.session_state['monitor_source_choice'] = ['water_level']
    st.session_state['monitor_sources'] = ('water_level',)
    st.session_state['workbench_entity_id'] = context['entity_id']
    st.session_state['workbench_reference'] = reference_key(context)
    st.session_state['workbench_reference_choice'] = reference_key(context)
    if context.get('measure_uri'):
        st.session_state['workbench_measure_choice'] = (reference_key(context), context['measure_uri'])
    st.session_state['workbench_layer_water'] = True
    st.session_state['workbench_layers'] = {**st.session_state.get('workbench_layers', {}), 'water': True}
    st.session_state['workbench_map_revision'] = st.session_state.get('workbench_map_revision', 0) + 1
    st.session_state['workbench_last_map_id'] = None


def open_data_context(context, tab):
    st.session_state['monitor_handoff'] = dict(context)
    st.session_state['data_handoff'] = dict(context)
    st.session_state['dashboard_page'] = 'Data'
    st.session_state['data_workspace_tab'] = tab
    if tab == 'Integration':
        st.session_state['integration_input_kind'] = 'Connected sources'
    st.session_state['data_source_search'] = ''
    source_id = context['source_id']
    st.session_state['data_source_id'] = source_id
    st.session_state['data_browse_' + source_id] = True
    water = context['source'] == 'water_level'
    st.session_state['data_table_' + source_id] = 'water_levels' if water else 'webtris_daily'
    st.session_state['data_quality_scope'] = 'Water levels' if water else 'Road traffic'
    for prefix in ['data_preview', 'data_quality']:
        st.session_state[prefix + '_mode'] = 'Historical browsing'
        st.session_state[prefix + '_dates_Historical browsing'] = tuple(pd.Timestamp(context[key]).date() for key in ['start', 'end'])


def clear_context(key):
    st.session_state.pop(key, None)


def filter_context_bundle(bundle, context):
    """Copy selected rows; leave cached source responses and timestamps unchanged."""
    result = dict(bundle)
    for table, time_column in [('water_levels', 'date_time'), ('webtris_daily', 'timestamp')]:
        frame = bundle.get(table, pd.DataFrame())
        if (table == 'water_levels') != (context['source'] == 'water_level'):
            result[table] = frame.iloc[:0].copy()
            continue
        fields = ['station_reference', 'unit', 'datum_uri'] if table == 'water_levels' else ['site_id']
        if table == 'water_levels' and context.get('measure_uri'):
            fields.append('measure_uri')
        mask = pd.Series(True, index=frame.index)
        for field in fields:
            values = frame.get(field, pd.Series('', index=frame.index)).fillna('').astype(str)
            if field == 'site_id':
                values = values.str.replace(r'\.0$', '', regex=True)
            mask &= values.eq(str(context[field]))
        result[table] = filter_dates(frame.loc[mask].copy(), time_column, context['start'], context['end'])
    sites = bundle.get('webtris_sites', pd.DataFrame())
    ids = sites.get('site_id', pd.Series('', index=sites.index)).astype(str).str.replace(r'\.0$', '', regex=True)
    result['webtris_sites'] = sites.loc[ids.eq(context.get('site_id', ''))].copy()
    status = bundle.get('status', pd.DataFrame())
    if 'connector_id' in status:
        prefix = ('ea_liverpool_tide_water_level', 'water_level_api') if context['source'] == 'water_level' else ('webtris',)
        result['status'] = status.loc[status['connector_id'].astype(str).str.startswith(prefix)].copy()
    return result


def workspace_context_summary():
    """Describe the active workspace without fetching or restoring a cleared context."""
    import json
    state=st.session_state
    page=state.get('dashboard_page','Overview')
    def result(label,start=None,end=None,basis='',mode=''):
        return {'label':label,'start':start,'end':end,'time_basis':basis,'mode':mode}
    def from_context(context,mode):
        label=str(context.get('entity_id') or 'Selected observations')
        if context.get('unit'):
            label+=' · '+str(context['unit'])+' · '+str(context.get('datum_uri',''))
        basis='UTC observations' if context.get('source')=='water_level' else 'Source timezone unverified'
        return result(label,context.get('start'),context.get('end'),basis,mode)
    if page=='Overview':
        today=pd.Timestamp.now(tz='Europe/London').date().isoformat()
        return result('Liverpool & Merseyside',today,today,
                      'Each feed retains its issue, valid or observation time','Current overview')
    if page=='Monitor':
        if state.get('monitor_data_mode','Example network')=='Example network':
            return result('Example network',basis='Illustrative scenario time',mode='Simulated demo')
        if state.get('monitor_data_mode')=='Weather & flood':
            return None
        context=dict(state.get('monitor_handoff') or {})
        identity=state.get('workbench_entity_id')
        if identity and context.get('entity_id')!=identity:
            context={'entity_id':identity,'source':'water_level' if identity.startswith('water:') else 'webtris'}
        context['start']=state.get('monitor_start',context.get('start'))
        context['end']=state.get('monitor_end',context.get('end'))
        return from_context(context,state.get('monitor_mode','Recent observations'))
    if page!='Data':
        return None
    context=state.get('data_handoff')
    if state.get('data_workspace_tab')!='Integration':
        return from_context(context,'Selected observations') if context else None
    kind=state.get('integration_input_kind','Connected sources')
    mode=state.get('integration_mode','Collected snapshot')
    metadata=state.get('integration_csv_metadata') or {}
    if kind=='Upload CSV':
        return result(metadata.get('filename') or metadata.get('label') or 'Uploaded CSV',
                      basis='Original CSV timestamps; actual upload time',mode=mode) if metadata else None
    loaded=state.get('integration_loaded') or {}
    try:
        signature=json.loads(loaded.get('signature') or '{}')
    except (TypeError,ValueError):
        signature={}
    if not isinstance(signature,dict) or (signature.get('context') and signature['context']!=context):
        signature={}
    if context:
        summary=from_context(context,mode)
    elif signature:
        sources=signature.get('sources') or []
        dates=state.get('integration_dates_traffic' if sources==['webtris'] else 'integration_dates')
        changed_sources=state.get('integration_sources',sources)!=sources
        changed_dates=dates and len(dates)==2 and tuple(str(value) for value in dates)!=(signature.get('start'),signature.get('end'))
        if changed_sources or changed_dates:
            return result('Collection settings changed',basis='Load selected records to update the product',mode='Awaiting collection')
        summary=result(' · '.join(sources),signature.get('start'),signature.get('end'),
                       'API request window; observation and retrieval times remain separate',mode)
    else:
        return None
    if kind=='Combine API + CSV' and metadata:
        summary['label']+=' + '+str(metadata.get('filename') or 'uploaded CSV')
        summary['time_basis']='API request window; CSV retains original observation timestamps'
    return summary
