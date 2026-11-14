"""Map presentation only: real geometry, source coordinates and explicit selection."""
import json
from urllib.parse import quote

import pydeck as pdk


_SOURCE = {'type': 'vector', 'url': 'https://tiles.openfreemap.org/planet'}
_NAME = ['coalesce', ['get', 'name:en'], ['get', 'name']]
_STYLE = {
    'version': 8, 'name': 'CRDT Maritime',
    'glyphs': 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    'sources': {'openmaptiles': _SOURCE},
    'layers': [
        {'id': 'land', 'type': 'background', 'paint': {'background-color': '#141A24'}},
        {'id': 'industrial-land', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'landuse',
         'filter': ['==', ['get', 'class'], 'industrial'], 'paint': {'fill-color': '#1D2532'}},
        {'id': 'water', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'water',
         'paint': {'fill-color': '#0C1420'}},
        {'id': 'shoreline', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'water',
         'paint': {'line-color': '#354555', 'line-width': .8}},
        {'id': 'waterway', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'waterway',
         'paint': {'line-color': '#354555', 'line-width': 1}},
        {'id': 'buildings', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'building', 'minzoom': 13,
         'paint': {'fill-color': '#293342', 'fill-outline-color': '#364252'}},
        {'id': 'roads', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['!=', ['get', 'class'], 'rail'],
         'paint': {'line-color': '#3C4859', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, .6, 15, 2]}},
        {'id': 'main-roads', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]],
         'paint': {'line-color': '#677386', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 15, 3]}},
        {'id': 'rail', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['==', ['get', 'class'], 'rail'],
         'paint': {'line-color': '#596377', 'line-width': 1, 'line-dasharray': [3, 2]}},
        {'id': 'water-names', 'type': 'symbol', 'source': 'openmaptiles', 'source-layer': 'water_name',
         'layout': {'text-field': _NAME, 'text-font': ['Noto Sans Regular'], 'text-size': 12},
         'paint': {'text-color': '#778FA7', 'text-halo-color': '#0C1420', 'text-halo-width': 1}},
        {'id': 'places', 'type': 'symbol', 'source': 'openmaptiles', 'source-layer': 'place',
         'filter': ['in', ['get', 'class'], ['literal', ['city', 'town', 'village', 'suburb', 'neighbourhood']]],
         'layout': {'text-field': _NAME, 'text-font': ['Noto Sans Regular'], 'text-size': 12},
         'paint': {'text-color': '#A3AFC0', 'text-halo-color': '#141A24', 'text-halo-width': 1.5}},
    ],
}

# Streamlit 1.57 expects a URL string, including for an application-owned style.
MARITIME_STYLE = 'data:application/json;charset=utf-8,' + quote(json.dumps(_STYLE, separators=(',', ':')))
MAP_LEGEND = '''<div class="port-map-legend">
<span><i style="background:#65A79C"></i>Current water</span>
<span><i style="background:#9E8BBF"></i>Other water states</span>
<span><i style="background:#6C9CC7"></i>Traffic</span>
<span><i style="background:#8A9BAF"></i>Illustrative</span>
<span><i style="background:#7C83FD"></i>Selected object</span>
</div>'''


def selected_map_object(event):
    objects = (event or {}).get('selection', {}).get('objects', {})
    for layer in ['monitoring-labels', 'monitoring-points']:
        if objects.get(layer):
            return objects[layer][0]
    return None


def monitoring_layers(points, selected_id=None):
    if points.empty:
        return []
    points = points.sort_values('entity_id').copy()
    points['color'] = points.apply(lambda row: [138, 155, 175, 230] if row['kind'] == 'Demonstration'
        else [108, 156, 199, 255] if row['kind'] == 'Traffic'
        else [101, 167, 156, 255] if row['state'] == 'Current' else [158, 139, 191, 255], axis=1)
    points['label_offset'] = points.groupby(['lat', 'lon']).cumcount().map(lambda i: [16, -15 + i * 28])
    points['label_border'] = points['entity_id'].eq(selected_id).astype(int) * 2
    selected = points[points['entity_id'].eq(selected_id)]
    layers = [
        pdk.Layer('ScatterplotLayer', selected, id='monitoring-glow', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=17, get_fill_color=[124, 131, 253], opacity=.12, pickable=False),
        pdk.Layer('ScatterplotLayer', points, id='monitoring-points', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=6, get_fill_color='color',
            stroked=True, get_line_color=[202, 211, 226, 200], line_width_min_pixels=1, pickable=True),
        pdk.Layer('TextLayer', points, id='monitoring-labels', get_position='[lon, lat]', get_text='name',
            get_pixel_offset='label_offset', get_size=12, get_color=[225, 232, 242],
            font_family=pdk.types.String('Arial, sans-serif'),
            get_text_anchor=pdk.types.String('start'), get_alignment_baseline=pdk.types.String('center'),
            background=True, get_background_color=[17, 23, 34, 240], background_padding=[5, 4],
            get_border_width='label_border', get_border_color=[124, 131, 253, 255], pickable=True),
    ]
    if not selected.empty:
        layers.append(pdk.Layer('ScatterplotLayer', selected, id='selected-object', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=11, filled=False, stroked=True,
            get_line_color=[124, 131, 253, 255], line_width_min_pixels=2, pickable=False))
    return layers
