import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


CORNERS = [[-3.02, 53.44], [-2.99, 53.44], [-2.99, 53.46], [-3.02, 53.46], [-3.02, 53.44]]


class WeatherLayerTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('weather_layers'), 'Shared weather grid helpers are required')
        import weather_layers
        return weather_layers

    def test_load_grid_preserves_local_metadata_and_missing_or_invalid_file_is_optional(self):
        module = self.module()
        sample = {'id': 'wind-v1', 'valid_at_utc': '2025-11-14T18:00:00Z', 'cells': []}
        with tempfile.TemporaryDirectory() as folder, patch.object(module, 'DATA_DIR', Path(folder)):
            self.assertIsNone(module.load_grid('Wind'))
            path = Path(folder) / 'ukv_liverpool_wind_sample.json'
            path.write_text(json.dumps(sample), encoding='utf-8')
            self.assertEqual(module.load_grid('Wind'), sample)
            path.write_text('not json', encoding='utf-8')
            self.assertIsNone(module.load_grid('Wind'))
            self.assertIsNone(module.load_grid('../Wind'))

    def test_rain_cells_keep_true_geometry_and_generic_click_fields_without_mutation(self):
        module = self.module()
        sample = {'cells': [{'row': 1, 'col': 2, 'corners': CORNERS, 'mm': 2.5}]}
        before = copy.deepcopy(sample)
        layers, legend = module.grid_layers('Rain', sample)
        grid = next(layer for layer in layers if layer.id == 'weather-grid')
        self.assertTrue(grid.pickable)
        self.assertEqual(grid.data[0]['corners'], CORNERS)
        self.assertEqual(grid.data[0]['id'], 'rain:1:2')
        self.assertIn('Rain', grid.data[0]['name'])
        self.assertIn('2.5', grid.data[0]['value'])
        self.assertEqual(sample, before)
        self.assertEqual(len(legend), 5)
        self.assertTrue(all(len(color) == 3 for _, color in legend))

    def test_wind_speed_has_distinct_fixed_colours_and_cardinal_arrows_point_downwind(self):
        module = self.module()
        rain_legend = module.grid_layers('Rain', {'cells': []})[1]
        for direction, axis, sign in [(0, 1, -1), (90, 0, -1), (180, 1, 1), (270, 0, 1)]:
            with self.subTest(direction=direction):
                sample = {'cells': [{'row': 0, 'col': 0, 'corners': CORNERS,
                                     'speed_m_s': 12.4, 'direction_from_deg': direction}]}
                layers, legend = module.grid_layers('Wind', sample)
                grid = next(layer for layer in layers if layer.id == 'weather-grid')
                self.assertIn('12.4', grid.data[0]['value'])
                shaft = next(layer for layer in layers if layer.id == 'weather-wind-shafts')
                self.assertFalse(shaft.pickable)
                self.assertGreater(sign * (shaft.data[0]['target'][axis] - shaft.data[0]['source'][axis]), 0)
                head = next(layer for layer in layers if layer.id == 'weather-wind-heads')
                self.assertEqual(head.data[0]['polygon'][0], shaft.data[0]['target'])
                self.assertNotEqual(legend, rain_legend)
                self.assertEqual(legend, module.grid_layers('Wind', {'cells': []})[1])

    def test_absent_direction_keeps_speed_field_without_invented_arrows(self):
        module = self.module()
        layers, _ = module.grid_layers('Wind', {'cells': [{'corners': CORNERS, 'speed_m_s': 0}]})
        self.assertEqual([layer.id for layer in layers], ['weather-grid'])
        self.assertIn('0', layers[0].data[0]['value'])

    def test_invalid_values_or_geometry_are_not_zero_filled_or_drawn(self):
        module = self.module()
        for value in (None, float('nan'), float('inf'), -1, True):
            with self.subTest(value=value):
                layers, _ = module.grid_layers('Rain', {'cells': [{'corners': CORNERS, 'mm': value}]})
                self.assertFalse(layers)
        for corners in ([], [[181, 53], [-3, 53], [-3, 54], [181, 53]], CORNERS[:-1]):
            layers, _ = module.grid_layers('Rain', {'cells': [{'corners': corners, 'mm': 1}]})
            self.assertFalse(layers)
        self.assertEqual(module.grid_layers('Unknown', None), ([], []))

    def test_existing_rain_sample_is_drawn_at_native_bounds(self):
        module = self.module()
        sample = module.load_grid('Rain')
        self.assertIsNotNone(sample)
        layers, _ = module.grid_layers('Rain', sample)
        self.assertEqual(len(layers[0].data), sample['cell_count'])
        self.assertEqual(layers[0].data[0]['corners'], sample['cells'][0]['corners'])


if __name__ == '__main__':
    unittest.main()
