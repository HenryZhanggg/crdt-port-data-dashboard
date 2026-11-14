import unittest

import pandas as pd

from port_map import monitoring_layers


class PortMapTests(unittest.TestCase):
    def test_colocated_labels_keep_true_positions_and_independent_ids(self):
        points = pd.DataFrame([
            {'entity_id': 'water:A', 'name': 'Water gauge A', 'kind': 'Water', 'state': 'Current', 'lat': 53.45, 'lon': -3.02, 'detail': 'Observed'},
            {'entity_id': 'water:B', 'name': 'Water gauge B', 'kind': 'Water', 'state': 'Stale', 'lat': 53.45, 'lon': -3.02, 'detail': 'Observed'},
        ])
        layers = monitoring_layers(points, 'water:B')
        labels = next(layer for layer in layers if layer.id == 'monitoring-labels').data
        self.assertEqual({row['entity_id'] for row in labels}, {'water:A', 'water:B'})
        self.assertTrue(all((row['lat'], row['lon']) == (53.45, -3.02) for row in labels))
        self.assertNotEqual(labels[0]['label_offset'], labels[1]['label_offset'])
        self.assertEqual([row.get('label_border') for row in labels], [0, 2])
        ring = next(layer for layer in layers if layer.id == 'selected-object')
        self.assertEqual([row['entity_id'] for row in ring.data], ['water:B'])
        self.assertFalse(ring.pickable)
        self.assertNotIn('label_offset', points)

    def test_empty_map_and_hidden_selection_do_not_create_objects(self):
        self.assertEqual(monitoring_layers(pd.DataFrame(), 'water:A'), [])
        points = pd.DataFrame([{'entity_id': 'traffic:1', 'name': 'Counter 1', 'kind': 'Traffic', 'state': 'Reference location', 'lat': 53.45, 'lon': -3.02}])
        layers = monitoring_layers(points, 'water:missing')
        self.assertFalse(any(layer.id == 'selected-object' for layer in layers))


if __name__ == '__main__':
    unittest.main()
