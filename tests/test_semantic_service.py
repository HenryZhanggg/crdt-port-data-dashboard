import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from rdflib import Literal, Namespace, RDF, RDFS


DEMO = Namespace("https://example.invalid/crdt-demo/")
BASE = Path(__file__).resolve().parents[1]


class SemanticDemoTests(unittest.TestCase):
    def test_local_semantic_service_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec("semantic_service"))

    def demo(self):
        import semantic_service
        self.assertTrue(hasattr(semantic_service, "SemanticDemo"))
        return semantic_service.SemanticDemo()

    def test_rdf_types_filter_entities_and_labels_come_from_graph(self):
        demo = self.demo()
        self.assertEqual({item["uri"] for item in demo.types()}, {
            "demo:Port", "demo:Terminal", "demo:Road",
            "demo:MonitoringStation", "demo:UtilityFacility",
        })
        self.assertEqual([item["entity_id"] for item in demo.entities("demo:Road")], ["demo:road_a"])
        self.assertEqual(len(demo.entities("demo:InfrastructureAsset")), 5)
        self.assertEqual(demo.entities("demo:Unknown"), [])
        demo.graph.set((DEMO.road_a, RDFS.label, Literal("Changed in RDF")))
        self.assertEqual(demo.entity("demo:road_a")["name"], "Changed in RDF")
        self.assertIn((DEMO.road_a, RDF.type, DEMO.Road), demo.graph)

    def test_demo_entities_have_approximate_coordinates_and_local_sources(self):
        demo = self.demo()
        self.assertEqual(len(demo.entities()), 5)
        for entity in demo.entities():
            self.assertTrue(entity["entity_id"].startswith("demo:"))
            self.assertTrue(53.3 < entity["lat"] < 53.6)
            self.assertTrue(-3.2 < entity["lon"] < -2.8)
            self.assertIn("approximate", entity["coordinate_note"].lower())
            self.assertTrue(all(source.startswith("demo:") for source in entity["source_ids"]))
        self.assertIn("not approved WP1", demo.metadata["ontology_status"])
        self.assertTrue(all(source["source_id"].startswith("demo:") for source in demo.sources))
        with self.assertRaises(KeyError):
            demo.entity("water:real-station")

    def test_typed_relations_have_validity_and_illustrative_evidence(self):
        demo = self.demo()
        relations = demo.relations()
        self.assertEqual(len(relations), 5)
        for relation in relations:
            self.assertEqual(relation["evidence_role"], "illustrative")
            self.assertTrue(relation["evidence_ref"].startswith("demo:"))
            self.assertLess(relation["valid_from"], relation["valid_to"])
        relation_types = {row["uri"]: row for row in demo.relation_types()}
        self.assertEqual(relation_types["demo:dependsOn"]["inverse_label"], "supports")
        self.assertEqual(len(demo.relations(relation_type="demo:partOf")), 2)
        self.assertEqual(demo.relations(start="2026-11-15", end="2026-11-16"), [])
        self.assertEqual(len(demo.relations(start="2026-11-14", end="2026-11-14")), 5)

    def test_reverse_relations_use_correct_neighbor_and_inverse_label(self):
        demo = self.demo()
        port = {row["neighbor_id"]: row for row in demo.related("demo:port_a")}
        self.assertEqual(port["demo:terminal_a"]["display_relation"], "contains")
        self.assertEqual(port["demo:gauge_a"]["display_relation"], "observed by")
        power = demo.related("demo:power_a", "demo:dependsOn")
        self.assertEqual(power[0]["neighbor_id"], "demo:terminal_a")
        self.assertEqual(power[0]["display_relation"], "supports")
        self.assertEqual(power[0]["direction"], "incoming")
        road = demo.related("demo:road_a", "demo:connectedTo")
        self.assertEqual(road[0]["neighbor_id"], "demo:terminal_a")
        self.assertEqual(road[0]["direction"], "outgoing")
        self.assertEqual(demo.related("demo:road_a", "demo:dependsOn"), [])

    def test_profiles_follow_rdf_class_and_have_distinct_products(self):
        demo = self.demo()
        expected = {"port_a": "activity", "terminal_a": "state", "road_a": "traffic",
                    "gauge_a": "observations", "power_a": "state"}
        for entity, view in expected.items():
            profile = demo.profile("demo:" + entity)
            self.assertIn(view, [tab["id"] for tab in profile["tabs"]])
            self.assertTrue(demo.products("demo:" + entity, view))
        self.assertEqual(demo.products("demo:road_a", "observations"), [])
        demo.graph.set((DEMO.road_a, RDF.type, DEMO.Terminal))
        self.assertEqual(demo.profile("demo:road_a")["type_uri"], "demo:Terminal")

    def test_gauge_series_preserves_missing_value_units_and_reference(self):
        demo = self.demo()
        product = demo.products("demo:gauge_a", "observations")[0]
        self.assertEqual(product["role"], "Illustrative observation")
        self.assertEqual(product["metrics"][0]["unit"], "m")
        self.assertEqual(product["metrics"][0]["datum"], "demo local datum (illustrative)")
        self.assertIn(None, [row["level"] for row in product["rows"]])
        self.assertIn("missing", product["quality"]["note"].lower())
        filtered = demo.products("demo:gauge_a", "observations", "2026-11-14T10:00:00Z", "2026-11-14T11:00:00Z")[0]
        self.assertEqual([row["timestamp"] for row in filtered["rows"]], [
            "2026-11-14T10:00:00Z", "2026-11-14T11:00:00Z"])
        self.assertIsNone(filtered["rows"][0]["level"])
        self.assertEqual(demo.products("demo:gauge_a", "observations", "2026-11-15", "2026-11-15"), [])

    def test_road_flow_and_speed_have_separate_units(self):
        demo = self.demo()
        products = demo.products("demo:road_a", "traffic")
        metrics = {metric["key"]: metric for product in products for metric in product["metrics"]}
        self.assertEqual(metrics["flow"]["unit"], "vehicles/hour")
        self.assertEqual(metrics["speed"]["unit"], "km/h")
        self.assertTrue(all(product["entity_id"] == "demo:road_a" for product in products))

    def test_port_statistics_keep_interval_meaning(self):
        product = self.demo().products("demo:port_a", "activity", "2026-11-14T11:00:00Z", "2026-11-14T11:30:00Z")[0]
        self.assertEqual(product["role"], "Illustrative statistic")
        self.assertEqual(product["kind"], "interval")
        self.assertIn("interval_start", product["rows"][0])
        self.assertIn("interval_end", product["rows"][0])

    def test_scenario_selection_filters_results_without_changing_observations(self):
        demo = self.demo()
        self.assertEqual({item["scenario_id"] for item in demo.scenarios}, {"demo:weather", "demo:service"})
        observations = demo.products("demo:gauge_a", "observations")
        weather = demo.products("demo:terminal_a", "scenario", scenario_id="demo:weather")
        service = demo.products("demo:terminal_a", "scenario", scenario_id="demo:service")
        self.assertTrue(weather and service)
        self.assertTrue(all(row["scenario_id"] == "demo:weather" for row in weather))
        self.assertTrue(all(row["role"] == "Illustrative model output" for row in weather))
        self.assertNotEqual(weather[0]["rows"], service[0]["rows"])
        self.assertEqual(observations, demo.products("demo:gauge_a", "observations", scenario_id="demo:service"))
        self.assertEqual(demo.products("demo:terminal_a", "scenario", scenario_id="demo:unknown"), [])

    def test_model_catalog_is_type_applicable_and_not_executable(self):
        demo = self.demo()
        for entity in demo.entities():
            models = demo.models(entity["entity_id"])
            self.assertTrue(models)
            for model in models:
                self.assertIn(entity["type_uri"], model["applicability_types"])
                self.assertEqual(model["status"], "not executable")
                self.assertTrue(model["status_reason"])
                self.assertTrue(model["required_products"])
                self.assertNotIn("command", model)
                self.assertNotIn("endpoint", model)

    def test_results_are_copies_and_invalid_time_window_is_rejected(self):
        demo = self.demo()
        product = demo.products("demo:gauge_a", "observations")[0]
        product["rows"][0]["level"] = 999
        self.assertNotEqual(demo.products("demo:gauge_a", "observations")[0]["rows"][0]["level"], 999)
        with self.assertRaises(ValueError):
            demo.products("demo:gauge_a", "observations", "2026-11-15", "2026-11-14")
        with self.assertRaises(ValueError):
            demo.relations(start="not-a-date")

    def test_loader_only_parses_fixed_local_turtle_data(self):
        import semantic_service
        self.assertTrue(hasattr(semantic_service, "SemanticDemo"))
        original = semantic_service.Graph.parse
        with patch.object(semantic_service.Graph, "parse", autospec=True, side_effect=original) as parse:
            demo = semantic_service.SemanticDemo()
        self.assertEqual(parse.call_count, 1)
        self.assertEqual(parse.call_args.kwargs["format"], "turtle")
        self.assertIn("data", parse.call_args.kwargs)
        self.assertNotIn("source", parse.call_args.kwargs)
        self.assertNotIn("location", parse.call_args.kwargs)
        with self.assertRaises(TypeError):
            semantic_service.SemanticDemo(ontology_path="https://example.org/ontology.ttl")
        self.assertFalse(hasattr(demo, "execute"))
        fixture = json.loads((BASE / "data/semantic_demo.json").read_text(encoding="utf-8"))
        self.assertTrue(all(product["provenance"]["source_id"].startswith("demo:") for product in fixture["products"]))


if __name__ == "__main__":
    unittest.main()
