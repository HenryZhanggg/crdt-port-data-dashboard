"""Selectable weather, flood and water overlays for the Liverpool map."""
import pandas as pd
import pydeck as pdk
import streamlit as st

import daily_service
import daily_views
import weather_layers
from port_map import MARITIME_STYLE


_OPTIONS = ('Wind', 'Rain', 'Flood areas', 'Water levels')
_NAPTAN = 'https://www.gov.uk/government/publications/national-public-transport-access-node-schema'
_OGL = 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'



def _inside_ring(lon, lat, ring):
    inside = False
    for (a, b, *_), (c, d, *_) in zip(ring, ring[1:]):
        if (b > lat) != (d > lat) and lon < a + (c-a)*(lat-b)/(d-b):
            inside = not inside
    return inside


def _contained_stops(geometry, stops):
    if not {'Latitude', 'Longitude', 'CommonName'} <= set(stops):
        return []
    bounds = []
    for feature in geometry['features']:
        shape = feature['geometry']
        polygons = shape['coordinates'] if shape['type'] == 'MultiPolygon' else [shape['coordinates']]
        for shell, *holes in polygons:
            xs, ys = zip(*(point[:2] for point in shell))
            bounds.append((min(xs), min(ys), max(xs), max(ys), shell, holes))
    points = []
    coordinates = stops[['Latitude','Longitude']].apply(pd.to_numeric,errors='coerce')
    for name, (lat, lon) in zip(stops['CommonName'], coordinates.itertuples(index=False,name=None)):
        if pd.isna(name) or pd.isna(lat) or pd.isna(lon):
            continue
        if any(w <= lon <= e and s <= lat <= n and _inside_ring(lon, lat, shell)
               and not any(_inside_ring(lon, lat, hole) for hole in holes)
               for w, s, e, n, shell, holes in bounds):
            points.append({'name': str(name), 'lat': float(lat), 'lon': float(lon)})
    return points

def _flood_controls(snapshot, namespace, load_bundle, views):
    flood = snapshot['flood_warnings']
    reference = daily_service.MERSEY_FLOOD_AREA
    warnings = daily_views._current_flood_areas(flood, pd.Timestamp.now(tz='UTC'))
    choices = {key: item['title'] for key, item in warnings.items()}
    choices.setdefault(reference['id'], reference['title'] + ' (reference area)')
    key = f'{namespace}_flood_area'
    if st.session_state.get(key) not in choices:
        st.session_state.pop(key, None)
    area = st.selectbox('Flood area', list(choices), format_func=choices.get, key=key)
    focus = daily_views._flood_map_focus(area, warnings)
    geometry = focus['geojson']
    warning = warnings.get(area)
    label = (warning.get('severity') or 'Flood advisory in the retrieved feed') if warning else 'Published flood reporting boundary'
    st.caption('Environment Agency · ' + str(label))
    if not geometry:
        st.info('The boundary is unavailable. Check the official Environment Agency source.')
    if geometry and load_bundle and 'transport' in views and st.checkbox(
            'Show public transport stops within the boundary', key=f'{namespace}_flood_stops'):
        raw = load_bundle(None, None, ('naptan',)).get('naptan', pd.DataFrame())
        focus['stops'] = _contained_stops(geometry, raw)
        if raw.empty:
            st.caption('Public transport stop data are unavailable.')
        else:
            st.caption(f"{len(focus['stops'])} mapped stops within the reporting boundary")
        st.link_button('NaPTAN source', _NAPTAN)
        st.caption('Department for Transport · Open Government Licence v3.0')
    with st.expander('Flood area source'):
        st.caption('This uses Environment Agency flood and river level data from the real-time data API (Beta).')
        if warning:
            daily_views._link('Selected Environment Agency advisory', warning.get('url'))
        daily_views._link('Official area information', 'https://check-for-flooding.service.gov.uk/target-area/' + area)
        daily_views._link('Environment Agency flood warnings', flood.get('source_url'))
        daily_views._link('Open Government Licence v3.0', _OGL)
    return focus


def _toggle_layer(namespace, layer):
    key = f'{namespace}_map_layer'
    st.session_state[key] = None if st.session_state.get(key) == layer else layer
    st.session_state.pop(f'{namespace}_grid_cell', None)
    st.session_state.pop(f'{namespace}_last_cell', None)


def _render_grid_map(sample, map_column, controls, layer, namespace, height):
    layers, legend = weather_layers.grid_layers(layer, sample)
    if not layers:
        return False
    west, south, east, north = sample['bbox']
    deck = pdk.Deck(layers=layers, map_style=MARITIME_STYLE,
        tooltip={'text': '{name}\n{value}'}, initial_view_state=pdk.ViewState(
            latitude=(north+south)/2, longitude=(east+west)/2, zoom=9.1))
    with map_column:
        event = st.pydeck_chart(deck, height=height, width='stretch', on_select='rerun',
            selection_mode='single-object', key=f'{namespace}_{layer}_grid')
    cells = {cell['id']: cell for cell in layers[0].data}
    picks = (event or {}).get('selection', {}).get('objects', {}).get('weather-grid', [])
    picked = picks[0].get('id') if picks else None
    cell_key, last_key = f'{namespace}_grid_cell', f'{namespace}_last_cell'
    if picked in cells and picked != st.session_state.get(last_key):
        st.session_state[cell_key] = picked
    st.session_state[last_key] = picked
    with controls:
        if layer == 'Wind':
            moment = daily_views._time(sample['valid_at_utc'])
            st.caption(f'Archived UKV · 10 m wind at {moment:%d %b %Y, %H:%M UTC} · Arrows point downwind')
        else:
            start = daily_views._time(sample['valid_from_utc'])
            end = daily_views._time(sample['valid_to_utc'])
            st.caption(f'Archived UKV · One-hour rainfall · {start:%d %b %Y, %H:%M}–{end:%H:%M} UTC')
        st.markdown(' '.join(
            f'<span style="display:inline-block;margin-right:.55rem;white-space:nowrap">'
            f'<span style="background:rgb({red},{green},{blue});display:inline-block;width:.65em;'
            f'height:.65em;border-radius:2px"></span> {label}</span>'
            for label, (red, green, blue) in legend
        ), unsafe_allow_html=True)
        selected = st.selectbox('Grid cell', list(cells), index=None,
            format_func=lambda cell: cells[cell]['name'], key=cell_key, placeholder='Select or click the map')
        if selected:
            st.metric(layer + ' in selected cell', cells[selected]['value'])
        with st.expander('Weather layer source'):
            st.caption('Archived UKV model forecast on the 2 km grid.')
            st.caption(sample['attribution'])
            st.link_button('Met Office UKV forecast archive', sample['source_catalogue_url'])
            st.link_button('Original forecast file', sample['source_url'])
            if layer == 'Wind':
                st.link_button('Original wind direction file', sample['sources']['direction']['url'])
            daily_views._link('Source licence', sample.get('licence_url'))
    return True


def render_layer_map(snapshot, namespace, *, series=(), selected=None, load_bundle=None, views=()):
    controls_column, map_column = st.columns([1, 3], gap='small')
    controls = controls_column.container(border=True, key=f'{namespace}_map_controls')
    layer = st.session_state.get(f'{namespace}_map_layer')
    height = 425 if namespace == 'monitor' else 360
    focus = None
    with controls:
        st.markdown('**Map layers**')
        for start in (0, 2):
            for column, option in zip(st.columns(2, gap='small'), _OPTIONS[start:start+2]):
                column.button(option, key=f'{namespace}_layer_{option}', width='stretch',
                    type='primary' if option == layer else 'secondary',
                    on_click=_toggle_layer, args=(namespace, option))
        if layer == 'Flood areas':
            focus = _flood_controls(snapshot, namespace, load_bundle, views)
        elif layer == 'Water levels':
            st.caption('Environment Agency monitoring stations' if series else 'No water level stations returned.')
        elif layer is None:
            st.caption('Select a layer to show it on the map.')
    if layer in ('Wind', 'Rain'):
        if _render_grid_map(weather_layers.load_grid(layer), map_column, controls, layer, namespace, height):
            return None
        controls.info('The model grid is unavailable.')
    with map_column:
        return daily_views._map(series if layer == 'Water levels' else (), selected, snapshot['place'],
            focus=focus, key_prefix=f'{namespace}_{layer or "base"}', height=height)


def render_weather_map(snapshot, load_bundle, views):
    if 'weather' not in views:
        return
    st.subheader('Weather & flood')
    tide = snapshot.get('tide', {})
    series = tide.get('series', [])
    selected = st.session_state.get('monitor_water_station')
    picked = render_layer_map(snapshot, 'monitor', series=series, selected=selected,
        load_bundle=load_bundle, views=views)
    if picked:
        st.session_state['monitor_water_station'] = picked
    if st.session_state.get('monitor_map_layer') == 'Water levels':
        entry = next((entry for entry in series if entry['id'] == (picked or selected)), None)
        if entry:
            st.caption(daily_views._place_label(entry))
            daily_views._link('Station data source', entry.get('source_url'))
