import copy
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

import daily_service


AREA_ID = '013WATMEWLW'
AREA_URI = 'https://environment.data.gov.uk/flood-monitoring/id/floodAreas/' + AREA_ID
RING = [[-3.02, 53.44], [-3.01, 53.44], [-3.01, 53.45], [-3.02, 53.44]]


def feature(geometry_type='Polygon'):
    coordinates = [copy.deepcopy(RING)]
    return {'type': 'Feature', 'properties': {'FWS_TACODE': AREA_ID, 'TA_NAME': 'Mersey Estuary'},
            'geometry': {'type': geometry_type,
                         'coordinates': [coordinates] if geometry_type == 'MultiPolygon' else coordinates}}


def response(payload=None, chunks=None, status=200, headers=None):
    result = MagicMock(status_code=status, headers=headers or {})
    result.__enter__.return_value = result
    result.iter_content.return_value = chunks if chunks is not None else [json.dumps(payload).encode()]
    return result


class FloodGeometryTests(unittest.TestCase):
    def loader(self):
        self.assertTrue(callable(getattr(daily_service, 'load_flood_area_geometry', None)),
                        'A selected flood-area geometry loader is required')
        daily_service.load_flood_area_geometry.clear()
        self.addCleanup(daily_service.load_flood_area_geometry.clear)
        return daily_service.load_flood_area_geometry

    def test_flood_warning_preserves_exact_area_and_polygon_source_references(self):
        area_uri = AREA_URI.replace('https://', 'http://')
        warning_uri = AREA_URI.replace('/floodAreas/', '/floods/')
        item = daily_service.parse_flood_warnings({'items': [{
            '@id': warning_uri, 'floodAreaID': AREA_ID, 'severityLevel': 3,
            'floodArea': {'@id': area_uri, 'polygon': area_uri + '/polygon'}}]})['items'][0]
        self.assertEqual(item.get('flood_area_id'), AREA_ID)
        self.assertEqual(item.get('flood_area_uri'), area_uri)
        self.assertEqual(item.get('polygon_uri'), area_uri + '/polygon')
        self.assertEqual(item['url'], warning_uri)

    def test_known_mersey_reference_does_not_claim_a_current_warning(self):
        reference = getattr(daily_service, 'MERSEY_FLOOD_AREA', {})
        self.assertEqual(reference.get('id'), AREA_ID)
        self.assertEqual(reference.get('title'), 'Mersey Estuary from Liverpool and Wirral to Widnes')
        self.assertEqual(reference.get('area_uri'), AREA_URI)
        self.assertEqual(reference.get('polygon_uri'), AREA_URI + '/polygon')
        self.assertFalse({'active', 'severity', 'severity_level', 'warning'} & set(reference))

    def test_polygon_and_multipolygon_preserve_coordinates_and_are_cached(self):
        load = self.loader()
        for geometry_type in ('Polygon', 'MultiPolygon'):
            with self.subTest(geometry_type=geometry_type):
                load.clear()
                payload = {'type': 'FeatureCollection', 'features': [feature(geometry_type)]}
                with patch('daily_service.requests.get', return_value=response(payload)) as get:
                    result = load(AREA_ID)
                    self.assertEqual(load(AREA_ID), result)
                self.assertEqual(result['status'], 'available')
                self.assertEqual(result['geojson'], payload)
                self.assertEqual(result['source_url'], AREA_URI + '/polygon')
                self.assertEqual(result['area_id'], AREA_ID)
                self.assertIsNotNone(result['checked_at'])
                self.assertNotIn('active', result)
                get.assert_called_once()
                self.assertEqual(get.call_args.args, (AREA_URI + '/polygon',))
                self.assertFalse(get.call_args.kwargs['allow_redirects'])
                self.assertTrue(get.call_args.kwargs['stream'])
                self.assertLessEqual(get.call_args.kwargs['timeout'][1], 10)

    def test_single_feature_or_bare_polygon_is_normalized_to_a_feature_collection(self):
        load = self.loader()
        for payload in (feature(), feature()['geometry']):
            with self.subTest(payload_type=payload['type']):
                load.clear()
                with patch('daily_service.requests.get', return_value=response(payload)):
                    result = load(AREA_ID)
                self.assertEqual(result['status'], 'available')
                self.assertEqual(result['geojson']['type'], 'FeatureCollection')
                self.assertEqual(result['geojson']['features'][0]['geometry'], feature()['geometry'])

    def test_invalid_area_identifiers_never_make_a_request(self):
        load = self.loader()
        for area_id in ('', '../013WATMEWLW', 'https://evil.test/area', 'A?redirect=elsewhere', 'A' * 65, None):
            with self.subTest(area_id=area_id), patch('daily_service.requests.get') as get:
                result = load(area_id)
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['geojson'])
                get.assert_not_called()

    def test_malformed_and_wrong_area_geometries_fail_without_fallback_shapes(self):
        load = self.loader()
        invalid = [
            {'type': 'FeatureCollection', 'features': []},
            {'type': 'Point', 'coordinates': [-3.01, 53.44]},
            {'type': 'Feature', 'properties': {}, 'geometry': None},
        ]
        for coordinates in ([], [[]], [[[-3, 53], [-2, 53], [-2, 54]]],
                            [[[181, 53], [-2, 53], [-2, 54], [181, 53]]],
                            [[[-3, 53], [-2, float('nan')], [-2, 54], [-3, 53]]],
                            [[[-3, 53], [-2, 53], [-1, 53], [-3, 53]]],
                            [[[-3, 53], [True, 53], [-2, 54], [-3, 53]]]):
            invalid.append({'type': 'Polygon', 'coordinates': coordinates})
        wrong_area = feature()
        wrong_area['properties']['FWS_TACODE'] = 'OTHER'
        invalid.append(wrong_area)
        wrong_crs = {'type': 'FeatureCollection', 'features': [feature()],
                     'crs': {'type': 'name', 'properties': {'name': 'EPSG:27700'}}}
        invalid.append(wrong_crs)
        for payload in invalid:
            with self.subTest(payload=payload):
                load.clear()
                with patch('daily_service.requests.get', return_value=response(payload)):
                    result = load(AREA_ID)
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['geojson'])

    def test_timeout_redirect_oversized_and_non_json_responses_are_soft_failures(self):
        load = self.loader()
        failures = [requests.Timeout('offline'), response(status=302),
                    response(headers={'Content-Length': str(2 * 1024 * 1024 + 1)}),
                    response(chunks=[b'x' * (2 * 1024 * 1024 + 1)]),
                    response(chunks=[b'<html>not available</html>'])]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                load.clear()
                kwargs = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': failure}
                with patch('daily_service.requests.get', **kwargs) as get:
                    result = load(AREA_ID)
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['geojson'])
                self.assertIsNotNone(result['checked_at'])
                get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
