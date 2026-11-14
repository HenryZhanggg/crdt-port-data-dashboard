import json
import unittest
from unittest.mock import patch
from urllib.parse import unquote
from xml.etree import ElementTree

from semantic_service import SemanticDemo
from semantic_views import _spatial_view


class GeographicNetworkTests(unittest.TestCase):
    def deck(self, relations=None, selected='demo:terminal_a'):
        service = SemanticDemo()
        with patch('streamlit.pydeck_chart', return_value={'selection':{}}) as chart:
            _spatial_view(service.entities(), service.relations() if relations is None else relations,
                          selected, 0)
        return json.loads(chart.call_args.args[0].to_json())

    def test_five_existing_assets_have_distinct_category_icons_at_source_coordinates(self):
        layers = {layer['id']:layer for layer in self.deck()['layers']}
        icons = layers.get('semantic_icons', {}).get('data', [])
        self.assertEqual(len(icons), 5)
        self.assertEqual(len({row['icon']['url'] for row in icons}), 5)
        expected = {row['entity_id']:(row['lon'],row['lat']) for row in SemanticDemo().entities()}
        self.assertEqual({row['entity_id']:(row['lon'],row['lat']) for row in icons}, expected)

    def test_svg_icons_supply_intrinsic_dimensions_for_browser_image_decoding(self):
        icons = next(layer['data'] for layer in self.deck()['layers'] if layer['id']=='semantic_icons')
        for row in icons:
            icon = row['icon']
            svg = ElementTree.fromstring(unquote(icon['url'].split(',',1)[1]))
            self.assertEqual(svg.get('width'),str(icon['width']))
            self.assertEqual(svg.get('height'),str(icon['height']))

    def test_every_explicit_edge_has_a_forward_arrow_and_predicate(self):
        layers = {layer['id']:layer for layer in self.deck()['layers']}
        arrows = layers.get('semantic_arrows', {}).get('data', [])
        self.assertEqual(len(arrows), 5)
        predicates = layers.get('semantic_predicates', {}).get('data', [])
        self.assertEqual({row['relation_id'] for row in arrows},
                         {row['relation_id'] for row in SemanticDemo().relations()})
        self.assertEqual({row['name'] for row in predicates},
                         {row['relation_label'] for row in SemanticDemo().relations()})
        for arrow in arrows:
            a, b = arrow['source'], arrow['target']
            tip = arrow['polygon'][0]
            base = [(arrow['polygon'][1][axis]+arrow['polygon'][2][axis])/2 for axis in (0,1)]
            self.assertGreater(sum((tip[i]-base[i])*(b[i]-a[i]) for i in (0,1)), 0)

    def test_selected_one_hop_edges_are_accented_and_others_muted(self):
        links = next((layer['data'] for layer in self.deck()['layers'] if layer['id']=='semantic_links'), [])
        self.assertEqual(len(links), 5)
        for edge in links:
            active = 'demo:terminal_a' in (edge['source_id'],edge['target_id'])
            self.assertEqual(edge['color'][:3], [124,131,253] if active else [95,110,132])

    def test_relationship_filter_cannot_add_an_undeclared_edge(self):
        relations = SemanticDemo().relations(relation_type='demo:dependsOn')
        layers = self.deck(relations)['layers']
        for layer_id in ['semantic_links','semantic_arrows','semantic_predicates']:
            records = next((layer['data'] for layer in layers if layer['id']==layer_id), [])
            self.assertEqual([row['relation_id'] for row in records], ['demo:terminal_depends_on_power'])

    def test_empty_relations_never_generate_proximity_dependencies(self):
        layers = {layer['id']:layer for layer in self.deck([])['layers']}
        self.assertEqual(layers.get('semantic_links', {}).get('data'), [])
        self.assertEqual(layers.get('semantic_arrows', {}).get('data'), [])


if __name__=='__main__':
    unittest.main()
