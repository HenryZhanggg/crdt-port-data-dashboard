"""Composable port workspace; partner packages are data, never executable plugins."""
from html import escape
from hashlib import sha1
import json
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from data_quality import quality_table
from module_contracts import compare_run_outputs, load_module_registry, package_template, validate_package
from monitoring_views import chart_style, select_water_series, state_badge, utc_label, water_level_figure
from port_map import MAP_LEGEND, MARITIME_STYLE, monitoring_layers, selected_map_object
from workbench_data import build_entities, choose_entity
from workspace_data import quality_findings


PANELS = ['Selected observations', 'Events & restrictions', 'Data quality', 'Dependencies', 'Scenario & impact', 'Module readiness', 'Source evidence']
DEFAULT_PANELS = ['Selected observations', 'Data quality', 'Events & restrictions', 'Module readiness']
TASKS = {
    'Transport congestion & logistics': ('T6.1', ['WP2', 'WP3', 'WP4'], ['Selected observations', 'Events & restrictions', 'Dependencies', 'Data quality']),
    'Incident response & recovery': ('T6.2', ['WP2', 'WP3', 'WP4', 'WP5'], ['Events & restrictions', 'Dependencies', 'Scenario & impact', 'Data quality']),
    'Severe-weather management': ('T6.3', ['WP2', 'WP3', 'WP5'], ['Selected observations', 'Events & restrictions', 'Scenario & impact', 'Data quality']),
    'Supply-chain disruption': ('T6.4', ['WP2', 'WP3', 'WP4'], ['Dependencies', 'Scenario & impact', 'Source evidence', 'Data quality']),
}


def apply_workbench_theme():
    st.markdown('''<style>
    .block-container {max-width:1800px; padding-top:3rem; padding-bottom:1.5rem;}
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:.65rem;}
    .workbench-header {display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;
        gap:.5rem 1rem; background:#142a3a; color:#e5eef4; padding:.75rem 1rem; border-left:3px solid #43b8bd;}
    .workbench-header > div {display:flex; align-items:center; flex-wrap:wrap; gap:.4rem 1.2rem;}
    .workbench-brand {font-size:1.05rem; font-weight:600; letter-spacing:.01em;}
    .workbench-subtitle, .workbench-region {font: .72rem/1.5 Consolas,monospace; letter-spacing:.04em; color:#b9cbd7;}
    .workspace-meta {display:flex; flex-wrap:wrap; justify-content:space-between; gap:.4rem 1rem;
        color:#536b7b; background:transparent; border:0; border-bottom:1px solid #cbd5df; border-radius:0;
        padding:.3rem 0 .5rem; margin:0; font: .73rem/1.5 Consolas,monospace; letter-spacing:.025em;}
    .st-key-workspace_toolbar {padding:.2rem .65rem .5rem; background:#f6f8fa; border-bottom:1px solid #cbd5df;}
    .st-key-workspace_toolbar [data-testid="stWidgetLabel"] p {font-size:.75rem; color:#536b7b;}
    .st-key-workspace_shortcuts [data-testid="stButton"] button {min-height:2.1rem;}
    .st-key-workspace_shortcuts [data-testid="stButton"] p {font-size:.78rem;}
    .st-key-workspace_shortcuts {max-width:720px;}
    .st-key-workbench_spatial, .st-key-workbench_inspector, [class*="st-key-workbench_panel_"] {
        background:#fff; border-radius:3px;}
    .workbench-panel-title {display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;
        gap:.35rem; padding-bottom:.45rem; border-bottom:1px solid #d8e1e8; color:#233e50;
        font:600 .75rem/1.5 Consolas,monospace; letter-spacing:.045em;}
    .workbench-panel-title span {font-size:.69rem; font-weight:400; color:#62798a;}
    .workbench-identity {font: .73rem/1.6 Consolas,monospace; color:#5a7080; overflow-wrap:anywhere;}
    .workbench-reading {font:500 1.8rem/1.25 Consolas,monospace; font-variant-numeric:tabular-nums; color:#183c51; margin:.2rem 0;}
    .workbench-reference {margin:.2rem 0; display:grid; grid-template-columns:75px minmax(0,1fr); gap:.35rem .6rem; font-size:.77rem;}
    .workbench-reference dt {color:#5a7080;}
    .workbench-reference dd {margin:0; font-family:Consolas,monospace; overflow-wrap:anywhere;}
    .port-map-context {display:flex; flex-wrap:wrap; justify-content:space-between; gap:.3rem;
        padding:.45rem .65rem; background:#0b263b; color:#bed8e8; font:.72rem/1.5 Consolas,monospace;}
    .port-map-legend {display:flex; flex-wrap:wrap; align-items:center; gap:.4rem 1rem;
        padding:.55rem .65rem; background:#0b263b; color:#c5d9e6; font-size:.73rem;}
    .port-map-legend span {display:inline-flex; align-items:center; gap:.35rem;}
    .port-map-legend i {display:inline-block; width:8px; height:8px; border-radius:50%;}
    .quality-note {border:0; border-left:2px solid #cbd5df; background:#f6f8fa; border-radius:0;
        padding:.4rem .55rem; margin:.2rem 0; gap:.5rem; font-size:.76rem;}
    .quality-note strong {font-family:Consolas,monospace; font-weight:500;}
    div[data-testid="stMetric"] {border:1px solid #cbd5df; border-top:2px solid #157985; border-radius:3px;
        min-height:65px; padding:.45rem .7rem;}
    [data-testid="stMetricValue"] {font:500 1.3rem/1.5 Consolas,monospace; font-variant-numeric:tabular-nums;}
    [data-testid="stMetricLabel"] p {font-size:.74rem;}
    div[data-testid="stButton"] button, [data-testid="stExpander"], .stPlotlyChart,
    div[data-testid="stDataFrame"] {border-radius:3px;}
    .stPlotlyChart {border:0; padding:0;}
    [data-testid="stCaptionContainer"] {color:#5a7080;}
    [data-testid="stSidebar"] {background:#e5ebf0; border-right:1px solid #cbd5df;}
    [data-testid="stSidebar"] h1 {font-size:1.2rem; line-height:1.4;}
    .st-key-semantic_heading h3 {font-size:1.3rem; padding:.15rem 0;}
    .st-key-semantic_heading [data-testid="stVerticalBlock"] {gap:.15rem;}
    .st-key-semantic_context {background:#fff; border:1px solid #cbd5df; border-left:3px solid #157985;
        border-radius:3px; padding:.45rem .75rem .6rem;}
    .st-key-semantic_context [data-testid="stWidgetLabel"] p,
    .st-key-semantic_spatial [data-testid="stWidgetLabel"] p,
    .st-key-semantic_objects [data-testid="stWidgetLabel"] p {font-size:.75rem; color:#536b7b;}
    .st-key-semantic_objects, .st-key-semantic_spatial, .st-key-semantic_inspector,
    .st-key-semantic_content, .st-key-semantic_analysis {background:#fff; border-radius:3px;}
    .st-key-semantic_objects, .st-key-semantic_inspector, .st-key-semantic_analysis {gap:.45rem;}
    .st-key-semantic_objects [data-testid="stButton"] button,
    .st-key-semantic_inspector [data-testid="stButton"] button {min-height:2.25rem; text-align:left;}
    .st-key-semantic_objects [data-testid="stButton"] p,
    .st-key-semantic_inspector [data-testid="stButton"] p {font-size:.8rem; line-height:1.35;}
    [class*="st-key-semantic_"] [data-testid="stCaptionContainer"] p {color:#536b7b; font-size:.75rem; line-height:1.45;}
    .st-key-semantic_inspector pre {white-space:pre-wrap; overflow-wrap:anywhere; font-size:.75rem;}
    .st-key-semantic_content [data-testid="stTabs"] {gap:.35rem;}
    .st-key-semantic_content [data-testid="stTab"] {font-size:.8rem;}
    .semantic-status {display:flex; flex-wrap:wrap; gap:.35rem .5rem; color:#466172;
        font: .68rem/1.5 Consolas,monospace; letter-spacing:.025em;}
    .semantic-status span {padding:.15rem .45rem; background:#eaf1f5; border:1px solid #ccdae3; border-radius:2px;}
    .semantic-legend {display:flex; flex-wrap:wrap; gap:.35rem 1rem; color:#466172; font-size:.72rem;}
    .semantic-legend span {display:inline-flex; align-items:center; gap:.4rem;}
    .semantic-legend i {display:inline-block; flex-shrink:0; background:#157985;}
    .semantic-node {width:8px; height:8px; border-radius:50%;}
    .semantic-edge {width:18px; height:3px;}
    .semantic-legend .semantic-muted {height:1px; background:#718a9a;}
    .semantic-fields {grid-template-columns:64px minmax(0,1fr); margin:.15rem 0; gap:.4rem .5rem;}
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .semantic-status),
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .semantic-fields),
    [class*="st-key-semantic_"] [data-testid="stMarkdownContainer"]:has(> .workbench-panel-title) {margin-bottom:0;}
    .st-key-semantic_inspector .semantic-fields dt {font:.75rem/1.55 sans-serif;}
    .st-key-semantic_inspector .semantic-fields dd {font:.78rem/1.55 Consolas,monospace;}
    .st-key-daily_heading h3 {font-size:1.5rem; padding:.15rem 0;}
    .st-key-daily_summary [data-testid="stMetric"] {background:#fff; border-top:2px solid #d4e1e7;}
    .st-key-daily_summary [data-testid="stMetricValue"] {font:600 1.45rem/1.4 sans-serif;}
    .st-key-daily_spatial, .st-key-daily_updates, .st-key-daily_content, .st-key-daily_places {
        background:#fff; border-radius:5px;}
    [class*="st-key-daily_"] [data-testid="stCaptionContainer"] p {color:#536b7b; font-size:.78rem; line-height:1.5;}
    [class*="st-key-daily_"] [data-testid="stMarkdownContainer"]:has(> .workbench-panel-title) {margin-bottom:0;}
    .daily-update-title {font-size:.9rem; line-height:1.45; font-weight:600;}
    .daily-source {font-size:.76rem; color:#536b7b; line-height:1.5;}
    @media (max-width:700px) {
        .block-container{padding-top:3rem;}
        .workbench-header {padding:.7rem;}
        .workbench-subtitle, .workbench-region, .workspace-meta {font-size:.7rem;}
        .st-key-workspace_toolbar {padding:.4rem;}
        .st-key-workspace_shortcuts [data-testid="stHorizontalBlock"] {flex-wrap:wrap; gap:.4rem;}
        .st-key-workspace_shortcuts [data-testid="stColumn"] {flex:1 1 135px; min-width:0;}
        .st-key-workbench_summary [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem;}
        .st-key-workbench_summary [data-testid="stColumn"] {width:auto; min-width:0;}
        .st-key-daily_summary [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem;}
        .st-key-daily_summary [data-testid="stColumn"] {width:auto; min-width:0;}
    }
    @media (pointer:coarse) {[data-testid="stButton"] button {min-height:44px;}}
    </style>''', unsafe_allow_html=True)


def navigate(section, page):
    st.session_state['workspace_section'] = section
    st.session_state[f'workspace_view_{section}'] = page


def render_shortcuts(sections, current_page):
    targets = [('Home', 'Monitoring', 'Overview'),
               ('Monitor', 'Monitoring', 'Live Monitoring'),
               ('Objects & dependencies', 'Models & Dependencies', 'Objects & Dependencies'),
               ('Scenarios & runs', 'Models & Dependencies', 'Scenarios & Runs'),
               ('Data & evidence', 'Data & Research', 'Dataset Catalogue'),
               ('WP modules', 'WP Delivery', 'Module Registry'),
               ('Port connections example', 'Models & Dependencies', 'Port connections example')]
    available = [(label, section, page) for label, section, page in targets if page in sections.get(section, [])]
    if not available:
        return
    primary = [target for target in available if target[2] in {'Overview', 'Live Monitoring'}]
    secondary = [target for target in available if target not in primary]
    with st.container(key='workspace_shortcuts'):
        columns = st.columns(len(primary) + bool(secondary), gap='small')
        for column, (label, section, page) in zip(columns, primary):
            column.button(label, key=f'shortcut_{page}', width='stretch',
                          type='primary' if page == current_page else 'secondary',
                          on_click=navigate, args=(section, page))
        if secondary:
            with columns[-1].popover('More views', width='stretch'):
                for label, section, page in secondary:
                    st.button(label, key=f'shortcut_{page}', width='stretch',
                              type='primary' if page == current_page else 'secondary',
                              on_click=navigate, args=(section, page))


def _remember_object():
    st.session_state['workbench_entity_id'] = st.session_state['workbench_entity_picker']
    st.session_state['workbench_map_revision'] = st.session_state.get('workbench_map_revision', 0) + 1


def _remember_layer(name, key):
    settings = dict(st.session_state.get('workbench_layers', {}))
    settings[name] = st.session_state[key]
    st.session_state['workbench_layers'] = settings


def _remember_panels():
    st.session_state['workbench_panel_preset'] = list(st.session_state['workbench_panels'])


def _remember_map_object(key):
    selected = selected_map_object(st.session_state.get(key))
    if selected:
        st.session_state['workbench_entity_id'] = selected['entity_id']


def _pick_object(entities, map_id=None):
    chosen = choose_entity(entities, st.session_state.get('workbench_entity_id'), map_id,
                           st.session_state.get('workbench_last_map_id'))
    st.session_state['workbench_entity_id'] = chosen
    st.session_state['workbench_last_map_id'] = map_id
    if chosen is None:
        st.info('No monitoring objects are available for this selection. Review the source responses or enable illustrative assets.')
        return None
    labels = entities.set_index('entity_id')['name'].to_dict()
    st.session_state['workbench_entity_picker'] = chosen
    entity_id = st.selectbox('Inspect an object', entities['entity_id'].tolist(), format_func=labels.get,
                            key='workbench_entity_picker', on_change=_remember_object)
    st.session_state['workbench_entity_id'] = entity_id
    return entities[entities['entity_id'].eq(entity_id)].iloc[0].to_dict()


def _map(bundle, assets, service_area):
    controls = st.columns(3)
    settings = st.session_state.get('workbench_layers', {})
    water = controls[0].checkbox('Water gauges', value=settings.get('water', True), key='workbench_layer_water',
        on_change=_remember_layer, args=('water', 'workbench_layer_water'))
    traffic = controls[1].checkbox('Traffic counters', value=settings.get('traffic', True), key='workbench_layer_traffic',
        on_change=_remember_layer, args=('traffic', 'workbench_layer_traffic'))
    demo = controls[2].checkbox('Demonstration assets', value=settings.get('demo', False), key='workbench_layer_demo',
        on_change=_remember_layer, args=('demo', 'workbench_layer_demo'))
    visible_bundle = dict(bundle)
    if not water:
        visible_bundle['water_levels'] = pd.DataFrame()
    else:
        reference = st.session_state.get('workbench_reference', st.session_state.get('workbench_reference_choice', ''))
        frame = visible_bundle.get('water_levels', pd.DataFrame())
        if reference and not frame.empty:
            keys = frame['station_reference'].astype(str) + '|' + frame['unit'].astype(str) + '|' + frame['datum_uri'].fillna('').astype(str)
            matching = frame[keys.eq(reference)]
            if not matching.empty:
                station = str(matching.iloc[0]['station_reference'])
                visible_bundle['water_levels'] = frame[~frame['station_reference'].astype(str).eq(station) | keys.eq(reference)]
    if not traffic:
        visible_bundle['webtris_sites'] = pd.DataFrame()
    entities = build_entities(visible_bundle, assets, demo)
    points = entities.dropna(subset=['lat', 'lon']).copy()
    points['detail'] = points['evidence_role'] + ' | ' + points['state']
    layers = []
    if demo and service_area:
        layers.append(pdk.Layer('GeoJsonLayer', service_area, id='demonstration-boundary', filled=True,
            get_fill_color=[108, 145, 162, 12], get_line_color=[137, 153, 168, 130], line_width_min_pixels=1, pickable=False))
    layers.extend(monitoring_layers(points, choose_entity(entities, st.session_state.get('workbench_entity_id'))))
    deck = pdk.Deck(map_style=MARITIME_STYLE,
        initial_view_state=pdk.ViewState(latitude=53.448, longitude=-3.015, zoom=11.3, pitch=0), layers=layers,
        tooltip={'text': '{name}\n{detail}', 'style': {'backgroundColor': '#0b263b', 'color': '#e1f1fa'}})
    # Native selections use row indices; reset them when visible membership changes.
    membership = '|'.join(sorted(points['entity_id']))
    key = 'workbench_map_' + sha1(membership.encode()).hexdigest()[:10] + f"_{st.session_state.get('workbench_map_revision', 0)}"
    st.markdown(f'<div class="port-map-context"><span>MARITIME MAP / LIVERPOOL</span><span>{len(points)} MAPPED OBJECTS</span></div>', unsafe_allow_html=True)
    event = st.pydeck_chart(deck, width='stretch', height=380, on_select=lambda: _remember_map_object(key),
        selection_mode='single-object', key=key)
    selected = selected_map_object(event)
    st.markdown(MAP_LEGEND, unsafe_allow_html=True)
    st.caption('Select a marker or label. Colours describe data, not risk; the white ring is selection, not coverage. Map: OpenFreeMap / OpenMapTiles / OpenStreetMap.')
    return entities, selected.get('entity_id') if selected else None


def _inspect(entity, bundle):
    if entity is None:
        return pd.DataFrame()
    st.markdown(f"**{entity['name']}**")
    st.markdown(f'<div class="workbench-identity">{escape(entity["kind"])} · {escape(entity["evidence_role"].upper())}'
                f'<br>{escape(entity["entity_id"])}</div>', unsafe_allow_html=True)
    chosen = pd.DataFrame()
    if entity['kind'] == 'Water':
        water = bundle.get('water_levels', pd.DataFrame())
        station = water[water['station_reference'].astype(str).eq(entity['station_reference'])]
        references = set(station['station_reference'].astype(str) + '|' + station['unit'].astype(str) + '|' + station['datum_uri'].fillna('').astype(str))
        reference = st.session_state.get('workbench_reference', st.session_state.get('workbench_reference_choice'))
        if reference not in references:
            reference = f"{entity['station_reference']}|{entity['unit']}|{entity['datum_uri']}"
        st.session_state['workbench_reference'] = reference
        chosen = select_water_series(station, label='Measurement reference', key='workbench_reference')
        st.session_state['workbench_reference_choice'] = st.session_state['workbench_reference']
        if chosen.empty:
            state_badge('Unknown time', 'No valid observation timestamps in this reference.')
        else:
            latest = chosen.iloc[-1]
            quality = quality_table({'water_levels': chosen}, pd.DataFrame(), pd.DataFrame()).iloc[0]
            value = f"{latest['value']:.3f} {latest['unit']}" if pd.notna(latest['value']) else 'Invalid / conflicting value'
            st.markdown(f'<div class="workbench-reading">{escape(value)}</div>', unsafe_allow_html=True)
            state_badge(quality['State'], 'Observation age is not a risk classification.')
            st.markdown('<dl class="workbench-reference">'
                f'<dt>Observed</dt><dd>{escape(utc_label(latest["date_time"]))}</dd>'
                f'<dt>Unit</dt><dd>{escape(str(latest["unit"]))}</dd>'
                f'<dt>Datum</dt><dd>{escape(str(latest.get("datum", "Unknown")))}</dd>'
                '<dt>Source</dt><dd>Environment Agency</dd></dl>', unsafe_allow_html=True)
            with st.expander('Evidence & provenance'):
                st.json({key: str(latest.get(key, 'Not provided')) for key in
                    ['station_reference', 'unit', 'datum', 'datum_uri', 'api_endpoint', 'retrieved_at_utc']})
                st.caption('SOSA/SHACL checks are available in Data Quality. Project-wide WP1 identity/ontology alignment is pending.')
    elif entity['kind'] == 'Traffic':
        state_badge(entity['state'], 'A road counter is not a direct measurement of port-gate queues.')
        frame = bundle.get('webtris_daily', pd.DataFrame())
        if not frame.empty and 'site_id' in frame:
            frame = frame[frame['site_id'].astype(str).str.replace(r'\.0$', '', regex=True).eq(entity['site_id'])].copy()
        if frame.empty:
            st.info('Reference location; no observations for this counter were returned in this request.')
        else:
            frame = frame.sort_values('timestamp')
            latest = frame.iloc[-1]
            for field, label in [('Total Volume', 'Latest vehicle count / 15 min'), ('Avg mph', 'Latest average speed (mph)')]:
                if field in latest:
                    st.metric(label, str(latest[field]))
            st.caption(f"Source timestamp: {latest['timestamp']}. Traffic timezone remains unverified unless explicitly checked upstream.")
        chosen = frame
    else:
        st.info('Illustrative asset. Its operational condition and dependencies have not been verified.')
        st.caption('Sample asset statuses are excluded from monitoring and impact calculations.')
    if pd.notna(entity['lat']) and pd.notna(entity['lon']):
        st.caption(f"Location: {entity['lat']:.5f}, {entity['lon']:.5f}")
    else:
        st.caption('Location unavailable; the object remains inspectable in the register.')
    return chosen


def _current_run():
    return st.session_state.get('partner_runs', {}).get(st.session_state.get('current_run_id'))


def _display_results(frame):
    display = frame.copy()
    for column in ['value', 'value_a', 'value_b', 'delta']:
        if column in display and any(isinstance(value, int) and abs(value) > 2 ** 53 - 1 for value in display[column]):
            display[column] = display[column].map(lambda value: None if pd.isna(value) else str(value))
    return display


def _result_panel(entity=None):
    run = _current_run()
    if run is None:
        st.info('No partner run selected. Import a WP3/4/5 result package in Scenarios & Runs to inspect published outputs.')
        return
    st.text(f"{run['model_name']} · {run['evidence_role'].upper()}")
    st.text(f"Scenario {run['scenario_id']} | Run {run['run_id']} | Model {run['model_version']}")
    outputs = pd.DataFrame(run['outputs'], dtype=object)
    if entity:
        outputs = outputs[outputs['entity_id'].eq(entity['entity_id'])]
    if outputs.empty:
        st.info('This run has no outputs for the selected object. Other entity IDs remain available in the run workspace.')
    else:
        st.dataframe(_display_results(outputs), hide_index=True, width='stretch')
    st.caption('Provider-supplied results use their own valid times. Observation-date filters do not resample model outputs.')


def _relations(entities, entity=None, graph=False):
    package = st.session_state.get('dependency_package')
    if package is None:
        st.info('No WP4 dependency package loaded. Shared types and spatial proximity do not establish an operational dependency.')
        return
    frame = pd.DataFrame(package['relationships'])
    start, end = st.session_state.get('monitor_start'), st.session_state.get('monitor_end')
    if start and end:
        begins = pd.to_datetime(frame['valid_from'], utc=True)
        ends = pd.to_datetime(frame['valid_to'], utc=True)
        frame = frame[begins.lt(pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=1)) &
                      (ends.isna() | ends.gt(pd.Timestamp(start, tz='UTC')))]
    if entity:
        frame = frame[frame['source_id'].eq(entity['entity_id']) | frame['target_id'].eq(entity['entity_id'])]
    st.text(f"{package['dataset_id']} v{package['version']} · {package['evidence_role']} · Ontology declared: {package['ontology_version']}")
    if frame.empty:
        st.info('No declared relationships match this object and observation-date window; this does not establish independence.')
        return
    known = set(entities['entity_id'])
    frame = frame.copy()
    frame['Endpoint alignment'] = frame.apply(lambda row: 'Both in workspace' if {row['source_id'], row['target_id']} <= known else 'Unmatched endpoint', axis=1)
    if graph:
        displayed = frame.head(30)
        nodes = sorted(set(displayed['source_id']) | set(displayed['target_id']))
        positions = {node: (math.cos(2 * math.pi * i / len(nodes)), math.sin(2 * math.pi * i / len(nodes))) for i, node in enumerate(nodes)}
        fig = go.Figure()
        for _, row in displayed.iterrows():
            x0, y0 = positions[row['source_id']]; x1, y1 = positions[row['target_id']]
            fig.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref='x', yref='y', axref='x', ayref='y',
                showarrow=True, arrowhead=2, arrowsize=1.2, arrowcolor='#6b8b9b', text='')
            if row['direction'] == 'bidirectional':
                fig.add_annotation(x=x0, y=y0, ax=x1, ay=y1, xref='x', yref='y', axref='x', ayref='y',
                    showarrow=True, arrowhead=2, arrowsize=1.2, arrowcolor='#6b8b9b', text='')
        fig.add_trace(go.Scatter(x=[positions[n][0] for n in nodes], y=[positions[n][1] for n in nodes],
            mode='markers+text', text=[escape(n) for n in nodes], textposition='top center',
            marker={'size': 18, 'color': ['#267f86' if n in known else '#a6adb8' for n in nodes]}, hoverinfo='text'))
        fig.update_xaxes(visible=False, range=[-1.4, 1.4]); fig.update_yaxes(visible=False, range=[-1.4, 1.4])
        st.plotly_chart(chart_style(fig, 360), width='stretch')
        st.caption(f'Graph: first {len(displayed)} matching relationships; directions come from the supplied package. No cascade or severity is inferred.')
    st.dataframe(frame, hide_index=True, width='stretch')


def render_workbench(bundle, assets, service_area, transport):
    table = quality_table(bundle, pd.DataFrame(), pd.DataFrame())
    observations = table[table['Kind'].eq('Observation')]
    findings = quality_findings(observations)
    with st.container(key='workbench_summary'):
        cards = st.columns(4, gap='small')
        cards[0].metric('Water measurement references', int(observations['Source'].str.startswith('Water ').sum()))
        cards[1].metric('Traffic reference locations', len(bundle.get('webtris_sites', pd.DataFrame())))
        cards[2].metric('Data checks to review', len(findings))
        cards[3].metric('Partner runs in session', len(st.session_state.get('partner_runs', {})))
    with st.expander('Workspace panels', expanded=False):
        visible = st.multiselect('Visible panels', PANELS, default=st.session_state.get('workbench_panel_preset', DEFAULT_PANELS),
                                key='workbench_panels', on_change=_remember_panels)
    left, right = st.columns([2.2, 1], gap='small')
    with left:
        with st.container(border=True, key='workbench_spatial'):
            st.markdown('<div class="workbench-panel-title">SPATIAL SITUATION <span>OBSERVATIONS / REFERENCE LOCATIONS</span></div>', unsafe_allow_html=True)
            entities, map_id = _map(bundle, assets, service_area)
        trend_slot = st.container(border=True, key='workbench_panel_trend') if 'Selected observations' in visible else None
    with right, st.container(border=True, key='workbench_inspector'):
        st.markdown('<div class="workbench-panel-title">OBJECT INSPECTOR <span>SELECTED REFERENCE</span></div>', unsafe_allow_html=True)
        entity = _pick_object(entities, map_id)
        selected = _inspect(entity, bundle)
    if trend_slot is not None:
        with trend_slot:
            st.markdown('<div class="workbench-panel-title">SELECTED OBSERVATIONS <span>ACTUAL SOURCE TIMESTAMPS</span></div>', unsafe_allow_html=True)
            if entity and entity['kind'] == 'Water' and not selected.empty:
                st.plotly_chart(water_level_figure(selected, 230), width='stretch', key='workbench_observation_plot')
                st.caption('Observed values; gaps retained. Open Observation Explorer for interval export.')
            elif entity and entity['kind'] == 'Traffic' and not selected.empty and 'Total Volume' in selected:
                fig = px.line(selected, x='timestamp', y='Total Volume', labels={'timestamp': 'Source time (timezone unverified)'})
                st.plotly_chart(chart_style(fig, 230), width='stretch')
            else:
                st.info('Select a monitoring object with returned observations to view its trend.')
    panels = [panel for panel in visible if panel != 'Selected observations']
    for first in range(0, len(panels), 2):
        for column, panel in zip(st.columns(2, gap='small'), panels[first:first + 2]):
            with column, st.container(border=True, key=f'workbench_panel_{panel.replace(" ", "_")}'):
                st.markdown(f'<div class="workbench-panel-title">{escape(panel.upper())}</div>', unsafe_allow_html=True)
                if panel == 'Events & restrictions':
                    st.info('An operational incident / restriction feed is not connected. No live event or closure is inferred from data age.')
                    if st.session_state.get('workbench_layer_demo'):
                        st.caption('Illustrative transport events have their own sample dates and an unspecified timezone.')
                        st.dataframe(transport, hide_index=True, width='stretch', height=230)
                elif panel == 'Data quality':
                    if findings.empty:
                        st.success('No configured findings in the returned observation streams.')
                    else:
                        st.dataframe(findings[['Priority', 'Source', 'Finding']], hide_index=True, width='stretch', height=260)
                    st.caption('Checks describe data usability; missing, stale and invalid values remain distinct.')
                elif panel == 'Dependencies':
                    _relations(entities, entity)
                elif panel == 'Scenario & impact':
                    _result_panel(entity)
                elif panel == 'Module readiness':
                    st.dataframe(pd.DataFrame([{'Module': row['module_id'], 'Delivery': row['title'], 'Status': row['implementation_status']} for row in load_module_registry()]), hide_index=True, width='stretch', height=270)
                else:
                    status = bundle.get('status', pd.DataFrame())
                    st.dataframe(status.reindex(columns=['source', 'status', 'records', 'last_call_utc']), hide_index=True, width='stretch')
                    st.caption('These are the feeds requested by this view, not a global availability check.')


def _import_package(key):
    with st.expander('Connect a partner result or dependency package', expanded=False):
        st.caption('Data-only JSON, up to 1 MB. Stored in this authorised browser session; no uploaded code or URL is executed.')
        kind = st.selectbox('Template type', ['model_run', 'dependencies'], key=f'{key}_template')
        st.download_button('Download illustrative contract template', json.dumps(package_template(kind), indent=2),
            f'CRDT_{kind}_template.json', 'application/json', key=f'{key}_download')
        upload = st.file_uploader('Partner JSON package', type=['json'], max_upload_size=1, key=f'{key}_upload')
        if st.button('Validate & add to this session', key=f'{key}_load', disabled=upload is None):
            try:
                raw = upload.getvalue()
                if len(raw) > 1_000_000:
                    raise ValueError('Package exceeds the 1 MB intake limit.')
                package = validate_package(json.loads(raw.decode('utf-8-sig')))
                if package['artifact_type'] == 'model_run':
                    runs = dict(st.session_state.get('partner_runs', {}))
                    existing = runs.get(package['run_id'])
                    if existing is not None and existing != package:
                        raise ValueError('This run ID already has different contents. Publish a new run ID to preserve provenance.')
                    if existing is None and len(runs) >= 10:
                        raise ValueError('This session already contains ten runs. Clear session packages before importing more.')
                    runs[package['run_id']] = package
                    st.session_state['partner_runs'] = runs
                else:
                    st.session_state['dependency_package'] = package
                st.success('Contract checked and package added. Provider claims and ontology alignment still require project review.')
            except (ValueError, UnicodeError, RecursionError) as error:
                st.error(f'Package rejected: {error}')
        if st.button('Clear session packages', key=f'{key}_clear'):
            for field in ['partner_runs', 'dependency_package', 'current_run_id', 'current_run_picker']:
                st.session_state.pop(field, None)
            st.rerun()


def render_objects(bundle, assets):
    st.subheader('Objects & dependencies')
    st.caption('WP1 types and identity rules · WP2 source alignment · WP4 dependency evidence and interoperability')
    demo = st.checkbox('Include illustrative assets', value=False, key='objects_demo')
    entities = build_entities(bundle, assets, demo)
    left, right = st.columns([1, 1.5])
    with left, st.container(border=True):
        entity = _pick_object(entities)
        _inspect(entity, bundle)
    with right, st.container(border=True):
        st.markdown('**DECLARED RELATIONSHIPS**')
        _relations(entities, entity, graph=True)
    with st.expander('Source-derived object register', expanded=False):
        st.dataframe(entities.drop(columns=['source_url'], errors='ignore'), hide_index=True, width='stretch')
        st.caption('Workspace IDs support this prototype. Matching names or coordinates do not establish WP1 identity equivalence.')
    _import_package('objects')


def _remember_run():
    st.session_state['current_run_id'] = st.session_state['current_run_picker']


def render_runs():
    st.subheader('Scenarios & runs')
    st.caption('WP3 model-chain outputs · WP4 cross-sector results · WP5 impact interpretation')
    st.info('Live scenario / recovery models are not connected. Import published partner outputs to inspect and compare; importing does not launch a model.')
    _import_package('runs')
    runs = st.session_state.get('partner_runs', {})
    if not runs:
        st.caption('No run packages in this session. Archived research remains available in Research & Replay.')
        return
    options = [None] + list(runs)
    current = st.session_state.get('current_run_id')
    st.session_state['current_run_picker'] = current if current in runs else options[0]
    st.selectbox('Current run', options, key='current_run_picker', on_change=_remember_run,
        format_func=lambda value: 'No run selected' if value is None else f"{value} | {runs[value]['scenario_id']}")
    run = _current_run()
    if run:
        _result_panel()
        with st.expander('Run inputs, versions and provider claims'):
            st.json({k: v for k, v in run.items() if k != 'outputs'})
            st.caption('Provider validation status is a declaration, not CRDT acceptance. Inspect matching entity IDs and metric meanings before use.')
    st.subheader('Compare published runs')
    if len(runs) < 2:
        st.caption('Import a second run for an explicit A/B comparison.')
        return
    left, right = st.columns(2)
    a = left.selectbox('Run A / baseline', list(runs), key='compare_run_a')
    b = right.selectbox('Run B', list(runs), index=1, key='compare_run_b')
    st.text(f"A: {runs[a]['scenario_id']} / {runs[a]['model_name']} | B: {runs[b]['scenario_id']} / {runs[b]['model_name']}")
    if a == b:
        st.info('Choose two different run IDs.')
        return
    try:
        compared = compare_run_outputs(runs[a], runs[b])
    except ValueError as error:
        st.warning('These runs cannot be compared under the output contract.')
        st.text(str(error))
        return
    st.dataframe(_display_results(compared), hide_index=True, width='stretch')
    st.caption('Delta = B minus A, only for matching entity, metric, unit and valid time under the same declared ontology version. Unmatched values are not filled with zero. Matching metadata does not establish scientific comparability.')
    records = pd.concat([pd.DataFrame(runs[a]['outputs'], dtype=object).assign(Run=a), pd.DataFrame(runs[b]['outputs'], dtype=object).assign(Run=b)])
    choices = records[['entity_id', 'metric', 'unit']].drop_duplicates().apply(tuple, axis=1).tolist()
    metric = st.selectbox('Result series', choices, format_func=lambda v: ' | '.join(v), key='result_series')
    plotted = records[records['entity_id'].eq(metric[0]) & records['metric'].eq(metric[1]) & records['unit'].eq(metric[2])].copy()
    plotted['valid_time'] = pd.to_datetime(plotted['valid_time'], utc=True)
    if any(isinstance(value, int) and abs(value) > 2 ** 53 - 1 for value in plotted['value']):
        st.info('Values exceed the chart’s precise integer range. Inspect the exact table or download the CSV.')
    else:
        fig = px.line(plotted.sort_values('valid_time'), x='valid_time', y='value', color='Run', markers=True,
                      labels={'valid_time': 'Result valid time (UTC)', 'value': escape(f'{metric[1]} ({metric[2]})')})
        st.plotly_chart(chart_style(fig), width='stretch')
    st.download_button('Download run comparison CSV', compared.to_csv(index=False), 'CRDT_run_comparison.csv', 'text/csv')


def render_modules():
    st.subheader('WP module handovers')
    st.caption('WP responsibility register: a WP may deliver multiple data products, models and views. Each consuming team owns its internal adaptation. Status describes this application, not consortium task completion.')
    modules = load_module_registry()
    selected = st.selectbox('Module', [row['module_id'] for row in modules], format_func=lambda value: next(f"{r['module_id']} · {r['title']}" for r in modules if r['module_id'] == value))
    module = next(row for row in modules if row['module_id'] == selected)
    st.markdown(f"**{module['owner']}** | {' · '.join(module['tasks'])}")
    st.caption(f"{module['delivery_type']} · {module['implementation_status']}")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown('**AVAILABLE IN THIS APPLICATION**')
        for item in module['available']:
            st.write('• ' + item)
        st.markdown('**INPUT CONTRACT**')
        for item in module['inputs']:
            st.write('• ' + item)
    with right, st.container(border=True):
        st.markdown('**PARTNER HANDOVER STILL NEEDED**')
        for item in module['pending']:
            st.write('• ' + item)
        st.markdown('**OUTPUT CONTRACT**')
        for item in module['outputs']:
            st.write('• ' + item)
    st.download_button('Download module handover register', json.dumps(modules, indent=2), 'CRDT_WP_module_handovers.json', 'application/json')
    _import_package('modules')


def _apply_task(name):
    st.session_state['workbench_panel_preset'] = TASKS[name][2]
    st.session_state.pop('workbench_panels', None)
    st.session_state['demonstrator_task'] = name
    navigate('Monitoring', 'Live Monitoring')


def render_demonstrators():
    st.subheader('Demonstrator tasks')
    st.caption('WP6 · T6.1–T6.5 · Draft task packages for a shared system; real-world demonstrations remain to be validated.')
    name = st.selectbox('Demonstrator task', list(TASKS))
    task, required, panels = TASKS[name]
    st.markdown(f'**{task} · {name}**')
    st.write('Required module contributions: ' + ', '.join(required))
    st.write('Suggested workbench panels: ' + ', '.join(panels))
    st.info('These presets organise inspection. Validated crisis, impact and recovery models, operational inputs and partner acceptance evidence are still required for an end-to-end demonstration.')
    st.button('Open this task in the workbench', type='primary', on_click=_apply_task, args=(name,))
    draft = {'status': 'DRAFT - not an accepted demonstration', 'task_id': task, 'task': name,
             'required_modules': required, 'panels': panels,
             'acceptance_requirements': ['Confirm user decision and permitted interventions with operational partners',
                 'Validate the required data coverage, units and time alignment', 'Record model versions, inputs and scientific validation',
                 'Check evidence distinctions, missing inputs and access constraints', 'Record user feedback and assign each issue to its module owner']}
    st.download_button('Download draft task package', json.dumps(draft, indent=2), f'CRDT_{task}_task_draft.json', 'application/json')


def render_governance():
    st.subheader('Governance handover')
    st.caption('WP7 · T7.1 deployment/management · T7.3 data governance (Lancaster and partners)')
    st.info('The shared password and partner-view selector do not provide institutional identity or server-side role authorisation.')
    controls = pd.DataFrame([
        {'Area': 'Application access', 'Implemented': 'Password gate before loading data', 'Handover needed': 'Institutional identity, server-side authorisation and audit ownership'},
        {'Area': 'Partner views', 'Implemented': 'Prototype navigation rules', 'Handover needed': 'Approved roles, per-product access and data-owner permission'},
        {'Area': 'Partner packages', 'Implemented': 'Schema checks; session-local data intake; no uploaded code execution', 'Handover needed': 'Provider identity, semantic alignment and scientific review'},
        {'Area': 'Data provenance', 'Implemented': 'Source/time metadata, diagnostics, observation/report exports', 'Handover needed': 'Reviewed retention, licences and cross-partner sharing rules'},
        {'Area': 'Service ownership', 'Implemented': 'Streamlit application and connector code', 'Handover needed': 'Named hosting, release, incident response and long-term maintenance teams'},
    ])
    st.dataframe(controls, hide_index=True, width='stretch')
    st.download_button('Download governance handover', json.dumps({'status': 'DRAFT - policy decisions pending', 'controls': controls.to_dict(orient='records')}, indent=2),
                       'CRDT_governance_handover_draft.json', 'application/json')
