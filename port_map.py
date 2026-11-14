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
        {'id': 'land', 'type': 'background', 'paint': {'background-color': '#112434'}},
        {'id': 'industrial-land', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'landuse',
         'filter': ['==', ['get', 'class'], 'industrial'], 'paint': {'fill-color': '#193347'}},
        {'id': 'water', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'water',
         'paint': {'fill-color': '#082f49'}},
        {'id': 'shoreline', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'water',
         'paint': {'line-color': '#24556d', 'line-width': .8}},
        {'id': 'waterway', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'waterway',
         'paint': {'line-color': '#24556d', 'line-width': 1}},
        {'id': 'buildings', 'type': 'fill', 'source': 'openmaptiles', 'source-layer': 'building', 'minzoom': 13,
         'paint': {'fill-color': '#223f53', 'fill-outline-color': '#2b4b60'}},
        {'id': 'roads', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['!=', ['get', 'class'], 'rail'],
         'paint': {'line-color': '#34566b', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, .6, 15, 2]}},
        {'id': 'main-roads', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary']]],
         'paint': {'line-color': '#52778c', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 15, 3]}},
        {'id': 'rail', 'type': 'line', 'source': 'openmaptiles', 'source-layer': 'transportation',
         'filter': ['==', ['get', 'class'], 'rail'],
         'paint': {'line-color': '#486576', 'line-width': 1, 'line-dasharray': [3, 2]}},
        {'id': 'water-names', 'type': 'symbol', 'source': 'openmaptiles', 'source-layer': 'water_name',
         'layout': {'text-field': _NAME, 'text-font': ['Noto Sans Regular'], 'text-size': 12},
         'paint': {'text-color': '#7ab6d1', 'text-halo-color': '#082f49', 'text-halo-width': 1}},
        {'id': 'places', 'type': 'symbol', 'source': 'openmaptiles', 'source-layer': 'place',
         'filter': ['in', ['get', 'class'], ['literal', ['city', 'town', 'village', 'suburb', 'neighbourhood']]],
         'layout': {'text-field': _NAME, 'text-font': ['Noto Sans Regular'], 'text-size': 12},
         'paint': {'text-color': '#a7becd', 'text-halo-color': '#112434', 'text-halo-width': 1.5}},
    ],
}

# Streamlit 1.57 expects a URL string, including for an application-owned style.
MARITIME_STYLE = 'data:application/json;charset=utf-8,' + quote(json.dumps(_STYLE, separators=(',', ':')))
MAP_LEGEND = '''<div class="port-map-legend">
<span><i style="background:#27d3df"></i>Current water</span>
<span><i style="background:#efb454"></i>Other water states</span>
<span><i style="background:#669fff"></i>Traffic</span>
<span><i style="background:#94a3b8"></i>Illustrative</span>
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
    points['color'] = points.apply(lambda row: [148, 163, 184, 230] if row['kind'] == 'Demonstration'
        else [102, 159, 255, 255] if row['kind'] == 'Traffic'
        else [39, 211, 223, 255] if row['state'] == 'Current' else [239, 180, 84, 255], axis=1)
    points['label_offset'] = points.groupby(['lat', 'lon']).cumcount().map(lambda i: [16, -15 + i * 28])
    points['label_border'] = points['entity_id'].eq(selected_id).astype(int) * 2
    layers = [
        pdk.Layer('ScatterplotLayer', points, id='monitoring-glow', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=15, get_fill_color='color', opacity=.13, pickable=False),
        pdk.Layer('ScatterplotLayer', points, id='monitoring-points', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=6, get_fill_color='color',
            stroked=True, get_line_color=[217, 241, 251, 235], line_width_min_pixels=1, pickable=True),
        pdk.Layer('TextLayer', points, id='monitoring-labels', get_position='[lon, lat]', get_text='name',
            get_pixel_offset='label_offset', get_size=12, get_color=[224, 239, 248],
            font_family=pdk.types.String('Consolas, monospace'),
            get_text_anchor=pdk.types.String('start'), get_alignment_baseline=pdk.types.String('center'),
            background=True, get_background_color=[9, 29, 45, 235], background_padding=[5, 4],
            get_border_width='label_border', get_border_color=[231, 247, 255, 255], pickable=True),
    ]
    selected = points[points['entity_id'].eq(selected_id)]
    if not selected.empty:
        layers.append(pdk.Layer('ScatterplotLayer', selected, id='selected-object', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=11, filled=False, stroked=True,
            get_line_color=[241, 249, 255, 255], line_width_min_pixels=2, pickable=False))
    return layers
