"""Geographic presentation of supplied assets and explicit, directed relations."""
import math
from urllib.parse import quote

import pydeck as pdk

from port_map import MARITIME_STYLE


_ICONS = {
    'demo:Port':'<path d="M12 3v15M8 6h8M5 12H3c0 6 4 9 9 9s9-3 9-9h-2M7 17l5 4 5-4"/>',
    'demo:Terminal':'<path d="M3 21V9l9-6 9 6v12M3 10h18M7 21v-7h10v7M12 3v7"/>',
    'demo:Road':'<path d="M7 3 3 21M17 3l4 18M12 3v3m0 4v4m0 4v3"/>',
    'demo:MonitoringStation':'<path d="M9 4a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0ZM12 7v10m0 0h.01M18 5h3m-3 5h2"/>',
    'demo:UtilityFacility':'<path d="m14 2-9 12h6l-1 8 9-12h-6Z"/>',
}


def network_deck(entities, relations, selected, visible_ids=None, evidence='Illustrative object'):
    """Keep geographic coordinates intact; never infer links from proximity."""
    ids = {row['entity_id']:row for row in entities}
    visible_ids = set(ids) if visible_ids is None else set(visible_ids)
    points = []
    counts = {}
    for row in entities:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="white" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+_ICONS.get(row['type_uri'], _ICONS['demo:MonitoringStation'])+'</g></svg>'
        active = row['entity_id']==selected
        location = (row['lon'],row['lat'])
        offset = counts.get(location,0)
        counts[location] = offset+1
        points.append(dict(row, label=row['name'].removesuffix(' (DEMO)'),
            icon={'url':'data:image/svg+xml;charset=utf-8,'+quote(svg), 'width':24, 'height':24, 'mask':True},
            color=[124,131,253,255] if active else [149,162,181,255 if row['entity_id'] in visible_ids else 85],
            border=[124,131,253,255] if active else [65,78,98,255],
            label_border=1 if active else 0,
            label_anchor='end' if row['lon'] < -3.0165 else 'start',
            label_offset=[-26,offset*28] if row['lon'] < -3.0165 else [26,offset*28]))
    links = []
    for relation in relations:
        a = ids[relation['source_id']]
        b = ids[relation['target_id']]
        source, target = [a['lon'],a['lat']], [b['lon'],b['lat']]
        active = selected in (relation['source_id'],relation['target_id'])
        # Work in local metres so arrow width and forward direction agree at this latitude.
        lon_scale = 111320*math.cos(math.radians((a['lat']+b['lat'])/2))
        dx, dy = (b['lon']-a['lon'])*lon_scale, (b['lat']-a['lat'])*111320
        length = math.hypot(dx,dy)
        if not length:
            continue
        ux, uy = dx/length, dy/length
        arrow = [a['lon']+.68*(b['lon']-a['lon']), a['lat']+.68*(b['lat']-a['lat'])]
        polygon = [[arrow[0]+ux*60/lon_scale, arrow[1]+uy*60/111320],
                   [arrow[0]+(-ux*40-uy*40)/lon_scale, arrow[1]+(-uy*40+ux*40)/111320],
                   [arrow[0]+(-ux*40+uy*40)/lon_scale, arrow[1]+(-uy*40-ux*40)/111320]]
        links.append(dict(relation, source=source, target=target, polygon=polygon,
            position=[(a['lon']+b['lon'])/2, (a['lat']+b['lat'])/2], name=relation['relation_label'],
            color=[124,131,253,245] if active else [95,110,132,125], width=2.6 if active else 1.2))
    layers = [
        pdk.Layer('LineLayer', links, id='semantic_links', get_source_position='source',
            get_target_position='target', get_color='color', get_width='width', width_min_pixels=1),
        pdk.Layer('PolygonLayer', links, id='semantic_arrows', get_polygon='polygon',
            get_fill_color='color', stroked=False),
        pdk.Layer('TextLayer', links, id='semantic_predicates', get_position='position', get_text='name',
            get_color='color', get_size=11, background=True, get_background_color=[17,23,34,235],
            background_padding=[4,3]),
        pdk.Layer('ScatterplotLayer', points, id='semantic_objects', get_position='[lon, lat]',
            radius_units=pdk.types.String('pixels'), get_radius=20, get_fill_color=[17,23,34,250],
            stroked=True, get_line_color='border', line_width_min_pixels=2, pickable=True),
        pdk.Layer('IconLayer', points, id='semantic_icons', get_position='[lon, lat]', get_icon='icon',
            get_color='color', get_size=23, pickable=True),
        pdk.Layer('TextLayer', points, id='semantic_labels', get_position='[lon, lat]', get_text='label',
            get_color='color', get_size=12, get_pixel_offset='label_offset',
            get_text_anchor='label_anchor', background=True, get_background_color=[17,23,34,235],
            background_padding=[5,3], get_border_width='label_border', get_border_color=[124,131,253], pickable=True),
    ]
    return pdk.Deck(layers=layers, map_style=MARITIME_STYLE,
        initial_view_state=pdk.ViewState(latitude=sum(row['lat'] for row in entities)/len(entities),
            longitude=sum(row['lon'] for row in entities)/len(entities), zoom=13.15),
        tooltip={'html':'<b>{name}</b><br/>'+evidence})
