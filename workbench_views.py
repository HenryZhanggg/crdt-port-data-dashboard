"""Composable port workspace; partner packages are data, never executable plugins."""
from html import escape
from hashlib import sha1
import json

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from data_quality import quality_table
from module_contracts import compare_run_outputs, package_template, validate_package
from monitoring_views import chart_style, select_water_series, state_badge, utc_label, water_level_figure
from port_map import MAP_LEGEND, MARITIME_STYLE, monitoring_layers, selected_map_object
from workbench_data import build_entities, choose_entity


def _remember_object():
    st.session_state['workbench_entity_id'] = st.session_state['workbench_entity_picker']
    st.session_state['workbench_map_revision'] = st.session_state.get('workbench_map_revision', 0) + 1


def _remember_layer(name, key):
    settings = dict(st.session_state.get('workbench_layers', {}))
    settings[name] = st.session_state[key]
    st.session_state['workbench_layers'] = settings


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
        st.info('No monitoring objects are available for this selection. Review the source responses and observation dates.')
        return None
    labels = entities.set_index('entity_id')['name'].to_dict()
    st.session_state['workbench_entity_picker'] = chosen
    entity_id = st.selectbox('Inspect an object', entities['entity_id'].tolist(), format_func=labels.get,
                            key='workbench_entity_picker', on_change=_remember_object)
    st.session_state['workbench_entity_id'] = entity_id
    return entities[entities['entity_id'].eq(entity_id)].iloc[0].to_dict()


def _map(bundle, assets, service_area, allow_demo=True):
    controls = st.columns(3 if allow_demo else 2)
    settings = st.session_state.get('workbench_layers', {})
    water = controls[0].checkbox('Water gauges', value=settings.get('water', True), key='workbench_layer_water',
        on_change=_remember_layer, args=('water', 'workbench_layer_water'))
    traffic = controls[1].checkbox('Traffic counters', value=settings.get('traffic', True), key='workbench_layer_traffic',
        on_change=_remember_layer, args=('traffic', 'workbench_layer_traffic'))
    demo = (controls[2].checkbox('Demonstration assets', value=settings.get('demo', False), key='workbench_layer_demo',
        on_change=_remember_layer, args=('demo', 'workbench_layer_demo')) if allow_demo else False)
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
    st.caption('Select a marker or label. Colours describe data, not risk; the violet ring is selection, not coverage. Map: OpenFreeMap / OpenMapTiles / OpenStreetMap.')
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
                st.caption('Detailed SOSA/SHACL checks are available in Data. Project-wide WP1 identity/ontology alignment is pending.')
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
        st.info('No partner run selected. Add a published result package in Data, then choose its run here.')
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


def _relations(entities, entity=None):
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
    st.dataframe(frame, hide_index=True, width='stretch')


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


def _remember_run():
    st.session_state['current_run_id'] = st.session_state['current_run_picker']


def render_runs(entity=None):
    runs = st.session_state.get('partner_runs', {})
    if not runs:
        st.caption('No published run packages in this session. Add a partner result package in Data to inspect and compare its outputs.')
        return
    options = [None] + list(runs)
    current = st.session_state.get('current_run_id')
    st.session_state['current_run_picker'] = current if current in runs else options[0]
    st.selectbox('Current run', options, key='current_run_picker', on_change=_remember_run,
        format_func=lambda value: 'No run selected' if value is None else f"{value} | {runs[value]['scenario_id']}")
    run = _current_run()
    if run:
        _result_panel(entity)
        if entity:
            with st.expander('All outputs in the selected run'):
                st.dataframe(_display_results(pd.DataFrame(run['outputs'], dtype=object)), hide_index=True, width='stretch')
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
