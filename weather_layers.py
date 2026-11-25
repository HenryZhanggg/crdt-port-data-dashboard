"""Native weather sample cells and downwind arrows, without spatial interpolation."""
from bisect import bisect_right
import json
import math
from pathlib import Path

import pydeck as pdk


DATA_DIR = Path(__file__).parent / 'data'
_FILES = {'Rain': 'ukv_liverpool_rain_sample.json', 'Wind': 'ukv_liverpool_wind_sample.json'}
_SCALES = {
    'Rain': ([.5, 2, 5, 10], [
        ('<0.5 mm / 1h', [229, 241, 252]), ('0.5–<2 mm / 1h', [174, 212, 239]),
        ('2–<5 mm / 1h', [104, 171, 218]), ('5–<10 mm / 1h', [54, 118, 183]),
        ('≥10 mm / 1h', [56, 62, 133])]),
    'Wind': ([5, 10, 15, 20], [
        ('<5 m/s', [228, 241, 218]), ('5–<10 m/s', [172, 211, 141]),
        ('10–<15 m/s', [115, 184, 133]), ('15–<20 m/s', [243, 196, 105]),
        ('≥20 m/s', [209, 130, 90])]),
}


def load_grid(layer):
    """Return local versioned metadata unchanged, or None when unavailable."""
    if layer not in _FILES:
        return None
    try:
        sample = json.loads((DATA_DIR / _FILES[layer]).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return sample if isinstance(sample, dict) and isinstance(sample.get('cells'), list) else None


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _corners_valid(corners):
    return (isinstance(corners, list) and len(corners) >= 4 and corners[0] == corners[-1]
        and all(isinstance(point, list) and len(point) == 2 and all(_number(v) for v in point)
                and -180 <= point[0] <= 180 and -89 < point[1] < 89 for point in corners)
        and len({tuple(point) for point in corners}) >= 3)


def _wind_arrow(corners, direction):
    points = corners[:-1]
    lon = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    lon_scale = 111320 * math.cos(math.radians(lat))
    width = (max(p[0] for p in points) - min(p[0] for p in points)) * lon_scale
    height = (max(p[1] for p in points) - min(p[1] for p in points)) * 111320
    length = min(width, height) * .55
    east, north = -math.sin(math.radians(direction)), -math.cos(math.radians(direction))
    source = [lon - east * length / 2 / lon_scale, lat - north * length / 2 / 111320]
    target = [lon + east * length / 2 / lon_scale, lat + north * length / 2 / 111320]
    head = [target]
    for sign in (-1, 1):
        head.append([target[0] - (east * .25 + sign * north * .12) * length / lon_scale,
                     target[1] - (north * .25 - sign * east * .12) * length / 111320])
    return {'source': source, 'target': target, 'polygon': head}


def grid_layers(layer, sample):
    """Return pickable cells and a fixed, layer-specific legend; arrows flow downwind."""
    if layer not in _SCALES:
        return [], []
    boundaries, scale = _SCALES[layer]
    legend = [(label, list(color)) for label, color in scale]
    cells, arrows = [], []
    for index, cell in enumerate((sample or {}).get('cells', [])):
        if not isinstance(cell, dict):
            continue
        amount = cell.get('mm' if layer == 'Rain' else 'speed_m_s')
        corners = cell.get('corners')
        if not _number(amount) or amount < 0 or not _corners_valid(corners):
            continue
        row, col = cell.get('row', index), cell.get('col', 0)
        direction = cell.get('direction_from_deg')
        has_direction = _number(direction) and 0 <= direction <= 360
        value = f'{amount:g} mm / 1h' if layer == 'Rain' else f'{amount:g} m/s'
        if layer == 'Wind' and has_direction:
            value += f' · from {direction:g}°'
        cells.append({**cell, 'id': f'{layer.lower()}:{row}:{col}', 'name': f'UKV {layer} cell {row}, {col}',
                      'value': value, 'fill_color': scale[bisect_right(boundaries, amount)][1] + [190]})
        if layer == 'Wind' and amount > 0 and has_direction:
            arrows.append(_wind_arrow(corners, direction))
    if not cells:
        return [], legend
    layers = [pdk.Layer('PolygonLayer', cells, id='weather-grid', get_polygon='corners',
        get_fill_color='fill_color', get_line_color=[132, 146, 158, 80], stroked=True,
        line_width_min_pixels=.45, pickable=True)]
    if arrows:
        layers.extend([
            pdk.Layer('LineLayer', arrows, id='weather-wind-shafts', get_source_position='source',
                get_target_position='target', get_color=[45, 76, 62, 230], get_width=1.4,
                width_min_pixels=1, pickable=False),
            pdk.Layer('PolygonLayer', arrows, id='weather-wind-heads', get_polygon='polygon',
                get_fill_color=[45, 76, 62, 230], stroked=False, pickable=False),
        ])
    return layers, legend
