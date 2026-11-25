"""Detailed Monitor map for forecast rainfall and official flood areas."""
import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

import daily_service
import daily_views
from port_map import MARITIME_STYLE


_SAMPLE = Path(__file__).with_name('data') / 'ukv_liverpool_rain_sample.json'
_NAPTAN = 'https://www.gov.uk/government/publications/national-public-transport-access-node-schema'
_OGL = 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'


def _archive_sample():
    if _SAMPLE.is_file():
        sample = json.loads(_SAMPLE.read_text(encoding='utf-8'))
        if sample.get('cells'):
            return sample
    return None


def _rain_forecast(snapshot):
    weather = snapshot['weather']
    now = pd.Timestamp.now(tz='UTC')
    hours = daily_views._rain_hours(daily_views._forecast_frame(weather, now))
    focus = None
    if hours:
        incoming = st.session_state.get('daily_map_focus',(None,None))
        requested_unavailable = incoming[0]=='rain' and incoming[1] not in hours
        if st.session_state.get('weather_map_rain_hour') not in hours:
            st.session_state.pop('weather_map_rain_hour',None)
        chosen = st.selectbox('Forecast hour (UTC)', list(hours), key='weather_map_rain_hour',
            index=None if requested_unavailable else 0, format_func=daily_views._rain_period)
        if chosen is None:
            st.info('The selected hour is no longer in the forecast. Choose another hour to display it.')
        else:
            focus = {'rain': hours[chosen]}
            st.metric('Forecast rainfall at the Liverpool point', f"{hours[chosen]['rain_mm']:g} mm")
            st.caption('One-hour model forecast for the marked point · MET Norway · CC BY 4.0')
    else:
        st.info('No upcoming hourly rainfall values are available.')
    daily_views._map([], None, snapshot['place'], focus=focus, key_prefix='weather_map_rain', height=425)
    with st.expander('Rain forecast source'):
        daily_views._source(weather)
        st.caption('MET Norway forecast · CC BY 4.0')
        daily_views._link('MET Norway Locationforecast', weather.get('source_url'))
        daily_views._link('CC BY 4.0', weather.get('license_url', 'https://creativecommons.org/licenses/by/4.0/'))


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


def _flood_map(snapshot, load_bundle, views):
    flood = snapshot['flood_warnings']
    reference = daily_service.MERSEY_FLOOD_AREA
    warnings = daily_views._current_flood_areas(flood,pd.Timestamp.now(tz='UTC'))
    choices = {key: item['title'] for key, item in warnings.items()}
    choices.setdefault(reference['id'], reference['title']+' (reference area)')
    kind, requested = st.session_state.get('daily_map_focus',(None,None))
    if kind=='flood':
        choices.setdefault(requested, requested+' (reference area)')
    if st.session_state.get('weather_map_flood_area') not in choices:
        st.session_state.pop('weather_map_flood_area',None)
    area = st.selectbox('Flood area', list(choices), format_func=choices.get, key='weather_map_flood_area')
    focus = daily_views._flood_map_focus(area,warnings)
    geometry = focus['geojson']
    warning = warnings.get(area)
    if warning:
        st.caption('Environment Agency · '+str(warning.get('severity') or 'Flood advisory in the retrieved feed'))
    else:
        st.caption('Environment Agency · Published flood reporting boundary')
    if not geometry:
        st.info('The boundary is unavailable. Check the official Environment Agency source.')
    if geometry and 'transport' in views and st.checkbox('Show public transport stops inside the boundary',
            key='weather_map_transport_points'):
        raw = load_bundle(None, None, ('naptan',)).get('naptan', pd.DataFrame())
        points = _contained_stops(geometry, raw)
        focus['stops'] = points
        if points:
            preview = ', '.join(point['name'] for point in points[:4])
            st.caption(f'{len(points)} mapped stops inside the reporting boundary · {preview}'+(' …' if len(points)>4 else ''))
        elif raw.empty:
            st.caption('Public transport stop data are unavailable.')
        else:
            st.caption('No returned public transport stops inside this boundary.')
        st.caption('Source: Department for Transport NaPTAN · Open Government Licence v3.0.')
        st.link_button('NaPTAN source', _NAPTAN)
    daily_views._map([], None, snapshot['place'], focus=focus, key_prefix=f'weather_map_flood_{area}', height=425)
    st.caption('This uses Environment Agency flood and river level data from the real-time data API (Beta).')
    st.caption('Map outlines show official reporting boundaries. Check official sources for incident impacts and transport closures.')
    with st.expander('Flood area source'):
        daily_views._source(flood)
        if warning:
            st.caption('Reviewed '+daily_views._when(warning.get('published_at'))+
                       ' · Updated '+daily_views._when(warning.get('updated_at')))
            daily_views._link('Selected Environment Agency advisory', warning.get('url'))
        daily_views._link('Official area information','https://check-for-flooding.service.gov.uk/target-area/'+area)
        daily_views._link('Environment Agency flood warnings', flood.get('source_url'))
        daily_views._link('Open Government Licence v3.0', _OGL)


def _archived_rain(sample):
    st.caption('Historical UKV model forecast · One-hour rainfall accumulation')
    issued, start, end = (f"{daily_views._time(sample[key]):%d %b %Y, %H:%M UTC}"
                          for key in ('model_run_utc','valid_from_utc','valid_to_utc'))
    st.caption(f'Model run {issued} · Valid {start} to {end}')
    west, south, east, north = sample['bbox']
    colours = [[162,211,241,145], [84,165,221,180], [49,119,206,200],
               [58,83,194,220], [104,69,191,230]]
    cells = []
    labels = []
    for i, cell in enumerate(sample['cells']):
        rain = cell['mm']
        ring = cell['corners']
        x = sum(point[0] for point in ring[:-1]) / (len(ring)-1)
        y = sum(point[1] for point in ring[:-1]) / (len(ring)-1)
        labels.append(f'{y:.3f}°, {x:.3f}°')
        cells.append({'id': i, 'corners': ring, 'value': f'{rain:.3f} mm',
            'colour': colours[min(int(rain),len(colours)-1)]})
    layer = pdk.Layer('PolygonLayer', cells, id='weather-archive-cells', get_polygon='corners',
        get_fill_color='colour', get_line_color=[185,207,229,120], line_width_min_pixels=1,
        stroked=True, filled=True, pickable=True, auto_highlight=True)
    deck = pdk.Deck(layers=[layer], map_style=MARITIME_STYLE, tooltip={'text': 'Forecast rainfall: {value}'},
        initial_view_state=pdk.ViewState(latitude=(north+south)/2, longitude=(east+west)/2, zoom=9.1))
    map_column, details = st.columns([2.6,1],gap='small')
    with map_column:
        event = st.pydeck_chart(deck, height=425, width='stretch', on_select='rerun',
            selection_mode='single-object', key='weather_map_ukv')
    picked = (event or {}).get('selection', {}).get('objects', {}).get('weather-archive-cells', [])
    if not picked:
        st.session_state.pop('weather_map_last_cell',None)
    elif picked[0].get('id') != st.session_state.get('weather_map_last_cell'):
        selected = picked[0]['id']
        if selected in range(len(cells)):
            st.session_state['weather_map_last_cell'] = selected
            st.session_state['weather_map_cell'] = selected
    with details, st.container(border=True):
        index = st.selectbox('Grid cell', range(len(cells)), format_func=labels.__getitem__, key='weather_map_cell')
        st.metric('Forecast rainfall in selected cell', cells[index]['value'])
        st.caption('Rainfall in one hour (mm)')
        st.markdown(' '.join(
            f'<span style="display:inline-block;margin-right:.55rem;white-space:nowrap">'
            f'<span style="background:rgb({red},{green},{blue});display:inline-block;width:.65em;'
            f'height:.65em;border-radius:2px"></span> {label}</span>'
            for (red,green,blue,_),label in zip(colours,('0–<1','1–<2','2–<3','3–<4','4+'))
        ),unsafe_allow_html=True)
    st.caption(sample['attribution'])
    st.link_button('UKV sample source', sample['source_url'])
    st.link_button('Source licence', sample['licence_url'])
    with st.expander('Sample provenance'):
        st.code(sample['source_sha256'])


def render_weather_map(snapshot, load_bundle, views):
    if 'weather' not in views:
        return
    st.subheader('Weather & flood')
    sample = _archive_sample()
    modes = ['Rain forecast', 'Flood areas']
    if sample:
        modes.append('Archived rainfall grid')
    incoming = st.session_state.get('daily_map_focus')
    if incoming and incoming != st.session_state.get('weather_map_applied_focus'):
        kind, identifier = incoming
        if kind == 'rain':
            st.session_state['weather_map_mode'] = 'Rain forecast'
            st.session_state['weather_map_rain_hour'] = identifier
        elif kind == 'flood':
            st.session_state['weather_map_mode'] = 'Flood areas'
            st.session_state['weather_map_flood_area'] = identifier
        st.session_state['weather_map_applied_focus'] = incoming
    if st.session_state.get('weather_map_mode') not in modes:
        st.session_state.pop('weather_map_mode',None)
    mode = st.radio('Map layer', modes, horizontal=True, key='weather_map_mode')
    if mode == 'Rain forecast':
        _rain_forecast(snapshot)
    elif mode == 'Flood areas':
        _flood_map(snapshot, load_bundle, views)
    else:
        _archived_rain(sample)
