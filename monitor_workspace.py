"""One geographic workspace for examples and connected observations."""
from hashlib import sha1

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_quality import filter_dates, quality_table
from monitoring_views import chart_style, utc_label, water_level_figure
from semantic_views import render_semantic_demo
from workbench_views import _inspect, _map, _pick_object, _relations, render_runs
from workspace_data import quality_findings


def _remember_sources():
    st.session_state['monitor_sources'] = tuple(st.session_state['monitor_source_choice'])


def _water_readings(chosen):
    if chosen.empty:
        st.info('No water observations with valid timestamps were returned for this reference.')
        return
    if len(chosen) > 1:
        identity = '|'.join(str(chosen.iloc[0].get(k, '')) for k in ['station_reference', 'unit', 'datum_uri'])
        identity += '|' + '|'.join(chosen['date_time'].astype(str))
        first, last = st.select_slider('Visible observation interval', options=chosen['date_time'].tolist(),
            value=(chosen.iloc[0]['date_time'], chosen.iloc[-1]['date_time']),
            format_func=lambda t: t.strftime('%d %b %H:%M UTC'), key='monitor_interval_' + sha1(identity.encode()).hexdigest()[:12])
        chosen = chosen[chosen['date_time'].between(first, last)].reset_index(drop=True)
    row = chosen.iloc[-1]
    quality = quality_table({'water_levels': chosen}, pd.DataFrame(), pd.DataFrame(), requested_sources=('water_level',)).iloc[0]
    cards = st.columns(3)
    cards[0].metric('Observed range', f"{chosen['value'].max() - chosen['value'].min():.3f} {row['unit']}")
    cards[1].metric('Missing 15-minute intervals', int(quality['Missing intervals']))
    rate = row['rate_per_hour']
    cards[2].metric('Latest valid change rate', f'{rate:+.2f} m/h' if pd.notna(rate) else 'Not available',
        help='Calculated only between consecutive 15-minute observations; gaps are not bridged.')
    st.plotly_chart(water_level_figure(chosen, 300), width='stretch', key='monitor_water_level')
    st.caption('Observed time is UTC. Shaded gaps contain no observed values; unit and vertical reference remain unchanged.')
    with st.expander('Rate of change and selected records'):
        fig = go.Figure(go.Bar(x=chosen['date_time'], y=chosen['rate_per_hour'], marker_color='#7C83FD'))
        fig.update_xaxes(title='Observation time (UTC)')
        fig.update_yaxes(title='Observed change rate (m/h)')
        st.plotly_chart(chart_style(fig, 230), width='stretch', key='monitor_water_rate')
        st.dataframe(chosen, hide_index=True, width='stretch')
    st.download_button('Download selected observations', chosen.to_csv(index=False).encode(),
        f"water_{row['station_reference']}_{chosen.iloc[0]['date_time'].date()}_{row['date_time'].date()}.csv", 'text/csv')
    st.caption('The interval selector controls exported rows. Plot zoom does not change the export.')
    with st.expander('Advanced replay'):
        if st.checkbox('Show observation replay', key='monitor_show_replay'):
            from research_views import render_replay
            render_replay({'water_levels': chosen})


def _traffic_readings(selected, bundle, entity):
    if selected.empty:
        st.info('No observations returned for this counter in the selected dates.')
        return
    frame = bundle.get('webtris_daily', pd.DataFrame())
    site_ids = frame['site_id'].astype(str).str.replace(r'\.0$', '', regex=True)
    others = [site for site in site_ids.drop_duplicates() if site != entity['site_id']]
    choices = st.multiselect('Traffic counters', others, key='monitor_traffic_counters_' + entity['site_id'],
                            help='Choose additional counters to compare. The inspected counter is always included.')
    compared = frame[site_ids.isin([entity['site_id'], *choices])].copy()
    for metric, label in [('Total Volume', 'Vehicles per 15-minute interval'), ('Avg mph', 'Average speed (mph)')]:
        if metric in compared and not compared.empty:
            fig = px.line(compared.sort_values('timestamp'), x='timestamp', y=metric, color='site_id',
                          labels={'timestamp': 'Source timestamp (timezone unverified)', metric: label})
            st.plotly_chart(chart_style(fig, 260), width='stretch', key='monitor_traffic_' + metric)
    st.caption('Traffic retains the source timezone. Counts and speeds describe road counters; they do not directly measure port-gate queues.')
    st.dataframe(selected, hide_index=True, width='stretch')
    st.download_button('Download selected traffic observations', selected.to_csv(index=False).encode(),
                       f"traffic_{entity['site_id']}.csv", 'text/csv')


def render_monitor_workspace(load_bundle, assets, service_area, views=None, refresh=None):
    mode = st.radio('Data view', ['Example network', 'Connected observations'], horizontal=True, key='monitor_data_mode')
    if mode == 'Example network':
        render_semantic_demo()
        return
    allowed = {'weather', 'transport', 'gis'} if views is None else set(views)
    available = [source for source, permission in [('water_level', 'weather'), ('webtris', 'transport')] if permission in allowed]
    if not available:
        st.info('No observation sources are enabled for this partner view.')
        return
    context = st.columns([1.3, 1.3, .5], vertical_alignment='bottom', gap='small')
    time_mode = context[0].radio('Time mode', ['Recent observations', 'Historical browsing'], horizontal=True, key='monitor_mode')
    today = pd.Timestamp.now(tz='UTC').date()
    first = (pd.Timestamp(today) - pd.Timedelta(days=1 if time_mode == 'Recent observations' else 6)).date()
    dates = context[1].date_input('Observation dates', value=(first, today), max_value=today,
                                 disabled=time_mode == 'Recent observations', key=f'monitor_dates_{time_mode}')
    refresh_requested = context[2].button('Refresh data', width='stretch')
    st.caption('Water uses UTC; traffic retains its source timezone. Up to seven days per request. Feeds are cached and do not poll continuously.')
    if len(dates) != 2:
        st.info('Select both a start date and an end date.')
        return
    if dates[0] > dates[1] or (dates[1] - dates[0]).days > 6:
        st.info('Choose a period of up to seven days to keep monitoring charts responsive.')
        return
    labels = {'water_level': 'Water levels', 'webtris': 'Traffic counters'}
    stored = st.session_state.get('monitor_source_choice', st.session_state.get('monitor_sources', available))
    st.session_state['monitor_source_choice'] = [source for source in stored if source in available]
    sources = st.multiselect('Observation sources', available, format_func=labels.get,
                            key='monitor_source_choice', on_change=_remember_sources)
    _remember_sources()
    if not sources:
        st.info('Select an observation source to inspect.')
        return
    start, end = (value.isoformat() for value in dates)
    st.session_state['monitor_start'], st.session_state['monitor_end'] = start, end
    if refresh_requested:
        if refresh is not None:
            refresh(tuple(sources), start, end)
        elif hasattr(load_bundle, 'clear'):
            load_bundle.clear()
    bundle = dict(load_bundle(start, end, tuple(sources)))
    bundle['water_levels'] = filter_dates(bundle.get('water_levels', pd.DataFrame()), 'date_time', start, end) if 'water_level' in sources else pd.DataFrame()
    bundle['webtris_daily'] = filter_dates(bundle.get('webtris_daily', pd.DataFrame()), 'timestamp', start, end) if 'webtris' in sources else pd.DataFrame()
    if 'webtris' not in sources:
        bundle['webtris_sites'] = pd.DataFrame()
    left, right = st.columns([2.4, 1], gap='small')
    with left, st.container(border=True, key='workbench_spatial'):
        st.markdown('<div class="workbench-panel-title">SPATIAL SITUATION · SOURCE OBSERVATIONS</div>', unsafe_allow_html=True)
        entities, map_id = _map(bundle, assets, service_area, allow_demo=False)
    with right, st.container(border=True, key='workbench_inspector'):
        st.markdown('**OBJECT INSPECTOR**')
        entity = _pick_object(entities, map_id)
        selected = _inspect(entity, bundle)
    readings, connections, results, evidence = st.tabs(['Readings', 'Connections', 'Results', 'Sources'])
    with readings:
        if entity is None:
            st.info('No monitoring objects are available for the selected source responses.')
        elif entity['kind'] == 'Water':
            _water_readings(selected)
        elif entity['kind'] == 'Traffic':
            _traffic_readings(selected, bundle, entity)
    with connections:
        if 'gis' in allowed:
            _relations(entities, entity)
        else:
            st.caption('Dependency inspection is not enabled for this partner view.')
    with results:
        render_runs(entity=entity)
    with evidence:
        if entity:
            st.text(f"{entity['entity_id']} · {entity['evidence_role']} · {entity['state']}")
            st.caption('Source-derived identifiers support this prototype; they do not establish approved ontology identity.')
            if entity.get('source_url'):
                st.link_button('Open observation source', entity['source_url'])
            if not selected.empty:
                key = 'water_levels' if entity['kind'] == 'Water' else 'webtris_daily'
                requested = ('water_level',) if entity['kind'] == 'Water' else ('webtris',)
                table = quality_table({key: selected}, pd.DataFrame(), pd.DataFrame(), requested_sources=requested)
                st.dataframe(table, hide_index=True, width='stretch')
                findings = quality_findings(table)
                if not findings.empty:
                    st.dataframe(findings, hide_index=True, width='stretch')
                times = selected['date_time'] if key == 'water_levels' else selected['timestamp']
                st.caption('Latest returned observation: ' + (utc_label(times.max()) if key == 'water_levels' else str(times.max()) + ' · source timezone unverified'))
        status = bundle.get('status', pd.DataFrame())
        if not status.empty:
            st.dataframe(status, hide_index=True, width='stretch')
            st.caption('Source check times describe this request; observation timestamps describe the measurements.')
