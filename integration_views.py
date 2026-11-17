"""Inspect collected observations and replay explicit availability rules."""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from data_integration import integration_archive, integration_snapshot, normalise_observations
from monitoring_views import chart_style
from workspace_links import clear_context, context_allowed, filter_context_bundle
from validation_views import render_provider_notice
from tabular_integration_views import render_csv_mapping
from model_input_views import render_model_input_builder


LABELS = {'water_level': 'Water levels · EA', 'webtris': 'Road traffic · WebTRIS'}
TIME_ASSUMPTIONS = {'Unverified — keep blocked': None, 'Assume UTC': 'UTC',
                    'Assume Europe/London': 'Europe/London'}
INTEGRATION_WORKSPACE_BUILD='2026-11-17.2'


def _reset_cutoff():
    for key in ['integration_cutoff_date', 'integration_cutoff_time']:
        st.session_state.pop(key, None)


def _scope_bundle(bundle, sources, handoff):
    result = dict(bundle)
    for source, tables in [('water_level', ['water_levels']), ('webtris', ['webtris_daily', 'webtris_sites'])]:
        if source not in sources:
            for table in tables:
                result[table] = pd.DataFrame()
    status = bundle.get('status', pd.DataFrame())
    if 'connector_id' in status:
        prefixes = tuple('ea_liverpool_tide_water_level' if source == 'water_level' else 'webtris' for source in sources)
        result['status'] = status.loc[status['connector_id'].astype(str).str.startswith(prefixes)].copy()
    return filter_context_bundle(result, handoff) if handoff else result


def _label(row):
    fields = [str(row.get(field, '')) for field in ['entity_id', 'metric', 'unit']]
    qualifier = str(row.get('qualifier', ''))
    if qualifier:
        fields.append(qualifier)
    datum = str(row.get('datum_uri', ''))
    if datum:
        fields.append('datum: ' + datum.rstrip('/').rsplit('/', 1)[-1].rsplit('#', 1)[-1])
    return ' · '.join([*fields, 'ref ' + str(row.get('series_id', '')).rsplit(':', 1)[-1][:6]])


def _show_outputs(records, snapshot, audit, rules):
    available = snapshot['status'].astype(str).str.startswith('Available')
    cards = st.columns(3)
    cards[0].metric('Selected series', len(snapshot))
    cards[1].metric('Available at cut-off', int(available.sum()))
    cards[2].metric('Need attention', int((~available).sum()))
    st.caption('Available means these configured data checks passed. Model suitability and scientific acceptance remain with the receiving team.')
    results, evidence, mapping = st.tabs(['Input snapshot', 'Record decisions', 'Meaning and rules'])
    with results:
        columns = ['entity_id', 'reference', 'metric', 'value', 'unit', 'status', 'age_minutes', 'event_time', 'measure_uri', 'datum_uri']
        display=snapshot.assign(reference=snapshot['series_id'].str.rsplit(':',n=1).str[-1].str[:6])
        st.dataframe(display.reindex(columns=columns), hide_index=True, width='stretch')
        st.caption('Missing, stale, conflicting and invalid inputs keep a missing output value. Last observed values stay in the audit; no zero fill or datum conversion is applied.')
        timeline = audit.loc[audit['event_time'].notna()].copy()
        if not timeline.empty:
            timeline['Series'] = timeline.apply(_label, axis=1)
            timeline['Decision'] = timeline['exclusion_reason'].replace('', 'Eligible observation')
            timeline.loc[timeline['selected'],'Decision']='Selected input'
            figure = px.scatter(timeline.head(2000), x='event_time', y='Series', color='Decision',
                                hover_data=['value', 'unit', 'time_basis', 'effective_available_at', 'selected'])
            figure.add_vline(x=pd.Timestamp(rules['cutoff']).timestamp() * 1000,
                             line_dash='dot', line_color='#A8AEFF')
            figure.update_xaxes(title='Observation time (UTC)')
            figure.update_yaxes(title=None)
            st.plotly_chart(chart_style(figure, min(420, 210 + 30 * len(snapshot))), width='stretch',
                            key='integration_timeline')
            st.caption('The timeline compares record timing, not the magnitudes of different variables. Up to 2,000 records are plotted; exports retain all selected records.')
    with evidence:
        st.caption('Inspect which records were available, excluded, or selected for this cut-off. Original timestamps and source evidence remain in the package.')
        decisions = audit['exclusion_reason'].replace('', 'Eligible observation')
        st.dataframe(decisions.value_counts().rename_axis('Decision').reset_index(name='Records'),
                     hide_index=True, width='stretch')
        st.dataframe(audit.drop(columns=['raw_record'], errors='ignore').head(200), hide_index=True, width='stretch')
        st.caption('Preview shows up to 200 rows; the audit CSV includes every selected source record.')
        st.download_button('Download record audit CSV', audit.to_csv(index=False).encode(),
                           'CRDT_integration_audit.csv', 'text/csv', key='integration_audit_download')
    with mapping:
        st.caption('Draft common observation fields preserve source identities and measurement meanings. This is a workbench profile, pending WP1 terminology agreement.')
        fields = ['source_id', 'entity_id', 'series_id', 'metric', 'unit', 'datum_uri', 'parameter',
                  'qualifier', 'measure_uri', 'source_uri', 'time_basis', 'availability_basis']
        st.dataframe(records.reindex(columns=fields).drop_duplicates(), hide_index=True, width='stretch')
        st.json(rules)
        st.markdown('**To agree with the receiving WP:** required variables and objects; accepted units and references; '
                    'time window and valid age; missing-data policy; model trigger; independent checking reference.')
    left, right = st.columns(2)
    left.download_button('Download input snapshot CSV', snapshot.to_csv(index=False).encode(),
                         'CRDT_input_snapshot.csv', 'text/csv', key='integration_snapshot_download')
    right.download_button('Download integration report ZIP', integration_archive(records, snapshot, audit, rules),
                          'CRDT_integration_report.zip', 'application/zip', key='integration_report_download')


def render_integration_workspace(load_bundle, views, refresh=None, handoff=None):
    st.markdown('**Historical + updating data**')
    st.caption('Integration workspace build: '+INTEGRATION_WORKSPACE_BUILD)
    st.caption('Collect records, inspect their common fields, set availability rules, then export a traceable input snapshot. '
               'Collection is on demand and session-only; download a package to retain it.')
    st.markdown('**1  Collect** → **2  Map identities and meaning** → **3  Check time and quality** → **4  Export inputs**')
    if 'raw_data' not in views:
        st.info('This workbench requires raw-data access in the selected partner view.')
        return
    input_kind=st.radio('Data input',['Connected sources','Upload CSV'],horizontal=True,
                        key='integration_input_kind',on_change=_reset_input_configuration)
    if input_kind=='Upload CSV':
        upload=render_csv_mapping(views)
        if upload is not None:
            _configure_input_snapshot(*upload)
        return
    allowed = [source for source, permission in [('water_level', 'weather'), ('webtris', 'transport')] if permission in views]
    if not allowed or (handoff and not context_allowed(handoff, views)):
        st.info('The requested sources are outside this partner view. Choose a permitted source or clear the observation context.')
        return
    if handoff:
        allowed = [handoff['source']]
    stored = st.session_state.get('integration_sources', allowed[:1])
    st.session_state['integration_sources'] = [source for source in stored if source in allowed] or allowed[:1]
    if handoff:
        st.session_state['integration_sources'] = allowed
    sources = st.multiselect('Sources to connect', allowed, format_func=LABELS.get,
                             key='integration_sources', disabled=bool(handoff))
    if not sources:
        st.info('Select a source before collecting records.')
        return
    today = pd.Timestamp.now(tz='UTC').date()
    traffic_only = sources == ['webtris']
    end = today - pd.Timedelta(days=45) if traffic_only else today
    dates_default = (end - pd.Timedelta(days=6 if traffic_only else 1), end)
    date_key = 'integration_dates_traffic' if traffic_only else 'integration_dates'
    if handoff:
        dates_default = tuple(pd.Timestamp(handoff[key]).date() for key in ['start', 'end'])
        date_key = 'integration_dates_context_' + handoff['start'] + '_' + handoff['end']
    dates = st.date_input('Collection dates', value=dates_default, max_value=today,
                          key=date_key, disabled=bool(handoff))
    st.caption('Up to seven calendar days per request. Water uses UTC. WebTRIS is historical and usually published '
               'about one month after collection; recent water and traffic may have no overlapping coverage.')
    if 'webtris' in sources:
        render_provider_notice('HS007')
    if len(dates) != 2 or dates[0] > dates[1] or (dates[1] - dates[0]).days > 6:
        st.info('Choose a complete date range of up to seven calendar days.')
        return
    first, last = (value.isoformat() for value in dates)
    signature = json.dumps({'sources': sources, 'start': first, 'end': last, 'context': handoff}, sort_keys=True)
    if st.button('Load selected records', type='primary', key='integration_load'):
        with st.spinner('Collecting the selected observations'):
            if refresh:
                refresh(tuple(sources), first, last)
            bundle = _scope_bundle(load_bundle(first, last, tuple(sources)), sources, handoff)
        st.session_state['integration_loaded'] = {'signature': signature, 'bundle': bundle,
                                                 'collected_at': pd.Timestamp.now(tz='UTC').isoformat()}
        for key in ['integration_series', 'integration_cutoff_date', 'integration_cutoff_time']:
            st.session_state.pop(key, None)
    loaded = st.session_state.get('integration_loaded')
    if not loaded or loaded['signature'] != signature:
        st.info('Choose sources and dates, then select Load selected records. Settings do not request feeds automatically.')
        return
    bundle = _scope_bundle(loaded['bundle'], sources, handoff)
    status = bundle.get('status', pd.DataFrame())
    with st.expander('Collection status and source checks'):
        st.caption('Collected in this session: ' + loaded['collected_at'])
        st.dataframe(status, hide_index=True, width='stretch')
        st.caption('Collection time proves when this dashboard retrieved records. It does not recover their original publication or receipt times.')
    timezone = None
    if 'webtris' in sources:
        assumption = st.selectbox('Traffic time assumption', list(TIME_ASSUMPTIONS), key='integration_traffic_timezone')
        timezone = TIME_ASSUMPTIONS[assumption]
        if timezone:
            st.warning('Traffic UTC conversion uses your stated time assumption. It is not a verified provider timezone.')
    records = normalise_observations(bundle, traffic_timezone=timezone)
    if records.empty:
        st.info('The requested reference has no returned observations in this period. Inspect collection status, choose older traffic dates, or clear the observation context.')
        check={'requested_sources':list(sources),'collection_period':{'start':first,'end':last},
               'collected_at':loaded['collected_at'],'observation_context':handoff,
               'collection_status':json.loads(status.to_json(orient='records',date_format='iso')),
               'result':'No input snapshot: the request returned no observations'}
        st.download_button('Download collection check JSON',json.dumps(check,indent=2).encode(),
                           'CRDT_collection_check.json','application/json',key='integration_collection_download')
        return
    collection={'collected_at':loaded['collected_at'],'requested_sources':list(sources),
                'collection_status':json.loads(status.to_json(orient='records',date_format='iso')),
                'collection_period':{'start':first,'end':last},'observation_context':handoff,
                'traffic_timezone_assumption':timezone}
    _configure_input_snapshot(records,collection)


def _reset_input_configuration():
    for key in ['integration_series','integration_cutoff_date','integration_cutoff_time']:
        st.session_state.pop(key,None)
    clear_context('data_handoff')


def _configure_input_snapshot(records,collection):
    series = records.drop_duplicates('series_id').set_index('series_id', drop=False)
    labels = {key: _label(row) for key, row in series.iterrows()}
    if 'integration_series' not in st.session_state:
        st.session_state['integration_series'] = list(labels)[:6]
    else:
        st.session_state['integration_series'] = [key for key in st.session_state['integration_series'] if key in labels]
    selected = st.multiselect('Measurement series', list(labels), format_func=labels.get, key='integration_series')
    if not selected:
        st.info('Choose at least one measurement series to construct an input snapshot.')
        return
    records = records.loc[records['series_id'].isin(selected)].copy()
    mode = st.radio('Availability basis', ['Collected snapshot', 'Replay scenario'], horizontal=True,
                    key='integration_mode', on_change=_reset_cutoff)
    replay = mode == 'Replay scenario'
    if replay:
        st.warning('SIMULATED REPLAY: receipt times and dropped records are constructed from the controls below. '
                   'This tests processing rules; it does not measure actual provider latency.')
    else:
        st.caption('Collected snapshot uses recorded dashboard retrieval times. Historical provider arrival times are unavailable; '
                   'a cut-off before collection cannot establish what was known then.')
    times = records['event_time'].dropna() if replay else records['available_at'].dropna()
    default_cutoff = times.max().ceil('min') if replay and not times.empty else pd.Timestamp(collection['collected_at']).ceil('min')
    controls = st.columns(3)
    cutoff_date = controls[0].date_input('Decision date (UTC)', value=default_cutoff.date(), key='integration_cutoff_date')
    cutoff_time = controls[1].time_input('Decision time (UTC)', value=default_cutoff.time().replace(tzinfo=None),
                                        step=60, key='integration_cutoff_time')
    freshness = controls[2].number_input('Maximum observation age (minutes)', min_value=1, max_value=10080,
                                        value=60, step=5, key='integration_freshness')
    st.caption('The initial cut-off rounds the relevant observation or collection time up to the next minute. Adjust it to inspect what the selected records support at another time.')
    delay, drop_every = 0, 0
    if replay:
        left, right = st.columns(2)
        delay = left.number_input('Simulated delivery delay (minutes)', min_value=0, max_value=10080,
                                   value=0, step=5, key='integration_delay')
        drop_every = right.number_input('Drop every Nth record (0 = none)', min_value=0, max_value=1000,
                                         value=0, step=1, key='integration_drop_every')
    cutoff = pd.Timestamp.combine(cutoff_date, cutoff_time).tz_localize('UTC')
    rules = {'cutoff': cutoff.isoformat(), 'freshness_minutes': int(freshness),
             'availability_mode': 'replay' if replay else 'retrieval', 'delay_minutes': int(delay),
             'drop_every': int(drop_every), 'traffic_timezone_assumption': collection.get('traffic_timezone_assumption'),
             'source_ids': sorted(records['source_id'].unique().tolist()), 'series_ids': selected,
             'requested_sources': collection['requested_sources'],
             'collection_status': collection['collection_status'],
             'observation_context': collection.get('observation_context'),
             'collection_period': collection.get('collection_period'), 'collected_at': collection['collected_at'],
             'profile_status': 'draft observation profile; pending WP1 terminology agreement',
             'purpose': 'candidate data input snapshot; no model execution or scientific acceptance',
             'input_collection': collection}
    snapshot, audit = integration_snapshot(records, cutoff, freshness_minutes=int(freshness),
                                            availability_mode=rules['availability_mode'],
                                            delay_minutes=int(delay), drop_every=int(drop_every))
    _show_outputs(records, snapshot, audit, rules)
    render_model_input_builder(records, snapshot, rules)
