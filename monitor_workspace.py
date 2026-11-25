"""One geographic workspace for examples and connected observations."""
from hashlib import sha1

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import daily_service
from data_quality import filter_dates, quality_table
from monitoring_views import chart_style, utc_label, water_level_figure
from semantic_views import render_semantic_demo
from workbench_views import _inspect, _map, _pick_object, _relations, render_runs
from workspace_data import quality_findings
from data_relation_views import render_data_relations
from workspace_links import (clear_context, context_allowed, context_label, filter_context_bundle,
                             open_data_context, reference_key)

MONITOR_WORKSPACE_BUILD = '2026-11-25.1'


def _remember_sources():
    st.session_state['monitor_sources'] = tuple(st.session_state['monitor_source_choice'])


def _change_sources():
    _remember_sources()
    clear_context('monitor_handoff')


def _context_notice(context, reason=None):
    st.caption('Observation context: ' + context_label(context))
    if reason:
        st.info(reason)
    st.button('Clear context and choose observations', key='monitor_clear_context',
              on_click=clear_context, args=('monitor_handoff',))


def _selected_context(entity, selected, start, end):
    if not entity or entity['kind'] not in {'Water', 'Traffic'}:
        return None
    water = entity['kind'] == 'Water'
    context = {'source': 'water_level' if water else 'webtris',
        'source_id': 'HS004' if water else 'HS007', 'entity_id': entity['entity_id'],
        'start': start, 'end': end}
    if water:
        row = selected.iloc[0].to_dict() if not selected.empty else entity
        context.update({field: str(row.get(field, '')) for field in ['station_reference', 'unit', 'datum_uri']})
        if pd.notna(row.get('measure_uri')) and row['measure_uri']:
            context['measure_uri'] = str(row['measure_uri'])
    else:
        context['site_id'] = entity['site_id']
    return context


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
    st.caption('Traffic counts are historical; [WebTRIS is usually published about one month after collection](https://webtris.highwaysengland.co.uk/Home/Faqs).')
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
    handoff = st.session_state.get('monitor_handoff')
    if handoff and (st.session_state.get('workbench_entity_id') != handoff['entity_id']
        or (handoff['source'] == 'water_level' and st.session_state.get('workbench_reference') != reference_key(handoff))):
        clear_context('monitor_handoff')
        handoff = None
    allowed = {'weather', 'transport', 'gis', 'raw_data'} if views is None else set(views)
    modes = ['Example network', 'Connected observations']
    if 'weather' in allowed:
        modes.append('Weather & flood')
    if st.session_state.get('monitor_data_mode') not in modes:
        st.session_state['monitor_data_mode'] = modes[0]
    mode = st.radio('Data view', modes, horizontal=True, key='monitor_data_mode')
    if mode == 'Example network':
        render_semantic_demo()
        return
    if mode == 'Weather & flood':
        from weather_map_views import render_weather_map
        render_weather_map(daily_service.load_daily_snapshot(),load_bundle,allowed)
        return
    if handoff and not context_allowed(handoff, allowed):
        _context_notice(handoff, 'The requested observation source is outside this partner view. Clear the context to choose an enabled source.')
        return
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
                            key='monitor_source_choice', on_change=_change_sources)
    _remember_sources()
    if not sources:
        st.info('Select an observation source to inspect.')
        return
    start, end = (value.isoformat() for value in dates)
    if handoff and (start != handoff['start'] or end != handoff['end'] or handoff['source'] not in sources):
        clear_context('monitor_handoff')
        handoff = None
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
    if handoff:
        requested = filter_context_bundle(bundle, handoff)
        table_key = 'water_levels' if handoff['source'] == 'water_level' else 'webtris_daily'
        if requested[table_key].empty:
            _context_notice(handoff, 'The requested measurement reference has no returned observations in this period. No alternative reference has been selected.')
            status = requested.get('status', pd.DataFrame())
            if not status.empty:
                st.dataframe(status, hide_index=True, width='stretch')
            return
        _context_notice(handoff)
    left, right = st.columns([2.4, 1], gap='small')
    with left, st.container(border=True, key='workbench_spatial'):
        st.markdown('<div class="workbench-panel-title">SPATIAL SITUATION · SOURCE OBSERVATIONS</div>', unsafe_allow_html=True)
        entities, map_id = _map(bundle, assets, service_area, allow_demo=False)
        if handoff and map_id and map_id != handoff['entity_id'] and map_id != st.session_state.get('workbench_last_map_id'):
            clear_context('monitor_handoff')
    with right, st.container(border=True, key='workbench_inspector'):
        st.markdown('**OBJECT INSPECTOR**')
        entity = _pick_object(entities, map_id)
        selected = _inspect(entity, bundle, handoff)
        selected_context = _selected_context(entity, selected, start, end)
        if selected_context:
            if 'raw_data' in allowed:
                st.button('Integrate selected data',key='monitor_integrate',on_click=open_data_context,
                          args=(selected_context,'Integration'),width='stretch',type='primary')
            st.button('View data source', key='monitor_view_source', on_click=open_data_context,
                      args=(selected_context, 'Sources'), width='stretch')
            st.button('Check data quality', key='monitor_check_quality', on_click=open_data_context,
                      args=(selected_context, 'Quality'), width='stretch')
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
            render_data_relations(bundle, selected_context, entities)
            st.markdown('**Partner-declared dependencies**')
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
