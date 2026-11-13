from copy import deepcopy
import importlib
import unittest

import pandas as pd


def model_run():
    return {
        "schema_version": "1.0", "module_id": "WP3", "artifact_type": "model_run",
        "scenario_id": "demo:weather", "run_id": "demo:run_a", "model_name": "Example model",
        "model_version": "example-1", "ontology_version": "example-unapproved-1",
        "generated_at": "2026-11-13T12:00:00Z", "input_products": [{"product_id": "demo:input", "version": "1"}],
        "evidence_role": "simulated", "validation_status": "unvalidated",
        "outputs": [{"entity_id": "demo:terminal_a", "metric": "service_loss", "value": 10,
                     "unit": "%", "valid_time": "2026-11-13T13:00:00Z"}],
        "notes": "Illustrative integration template, not a CRDT result",
    }


def dependencies():
    return {
        "schema_version": "1.0", "module_id": "WP4", "artifact_type": "dependencies",
        "dataset_id": "demo:dependencies", "version": "example-1", "ontology_version": "example-unapproved-1",
        "generated_at": "2026-11-13T12:00:00Z", "evidence_role": "declared",
        "relationships": [{"source_id": "demo:terminal_a", "target_id": "demo:road_a",
                           "relation_type": "demo:requires_access", "direction": "directed",
                           "evidence_ref": "demo:provider_note", "valid_from": "2026-11-13T12:00:00Z", "valid_to": None}],
    }


class ModuleContractsTests(unittest.TestCase):
    def setUp(self):
        try:
            self.contracts = importlib.import_module("module_contracts")
        except ModuleNotFoundError as error:
            self.fail(f"Module contracts must be implemented: {error}")

    def test_registry_contains_seven_accountable_handover_records(self):
        rows = self.contracts.load_module_registry()
        self.assertEqual([row["module_id"] for row in rows], [f"WP{i}" for i in range(1, 8)])
        for row in rows:
            for field in ["title", "owner", "delivery_type", "implementation_status"]:
                self.assertIsInstance(row[field], str)
                self.assertTrue(row[field].strip())
            for field in ["tasks", "available", "pending", "inputs", "outputs"]:
                self.assertIsInstance(row[field], list)
                self.assertTrue(row[field])
        by_id = {row["module_id"]: row for row in rows}
        self.assertIn("T1.2", by_id["WP1"]["tasks"])
        self.assertIn("T1.3", by_id["WP1"]["tasks"])
        self.assertNotIn("T3.5", by_id["WP3"]["tasks"])
        self.assertIn("T4.4", by_id["WP4"]["tasks"])
        self.assertIn("ID50", by_id["WP5"]["tasks"])
        self.assertIn("T7.3", by_id["WP7"]["tasks"])
        self.assertTrue(all("prototype" in row["implementation_status"].lower() for row in rows))

    def test_model_metadata_is_retained_without_mutating_the_upload(self):
        payload = model_run()
        payload["outputs"][0]["valid_time"] = "2026-11-13T14:00:00+01:00"
        original = deepcopy(payload)
        validated = self.contracts.validate_package(payload)
        self.assertEqual(payload, original)
        self.assertEqual(validated["model_version"], "example-1")
        self.assertEqual(pd.Timestamp(validated["outputs"][0]["valid_time"]), pd.Timestamp("2026-11-13T13:00Z"))
        validated["outputs"][0]["value"] = 123
        self.assertEqual(payload["outputs"][0]["value"], 10)

    def test_all_declared_model_providers_are_accepted(self):
        for provider in ["WP3", "WP4", "WP5"]:
            for role in ["simulated", "forecast", "estimated"]:
                payload = model_run()
                payload.update(module_id=provider, evidence_role=role, validation_status="validated_by_provider")
                self.assertEqual(self.contracts.validate_package(payload)["evidence_role"], role)

    def test_input_product_list_has_no_output_row_limit(self):
        payload = model_run()
        payload["input_products"] *= 5001
        try:
            validated = self.contracts.validate_package(payload)
        except ValueError as error:
            self.fail(f"Only output/relationship lists have a 5000-row limit: {error}")
        self.assertEqual(len(validated["input_products"]), 5001)

    def test_unknown_artifact_or_provider_and_missing_metadata_are_rejected(self):
        for field, value in [("schema_version", "2.0"), ("module_id", "WP8"), ("module_id", "WP2"),
                             ("artifact_type", "python"), ("evidence_role", "observation"),
                             ("validation_status", "project_approved")]:
            with self.subTest(field=field, value=value):
                payload = model_run()
                payload[field] = value
                with self.assertRaises(ValueError):
                    self.contracts.validate_package(payload)
        for field in ["scenario_id", "run_id", "model_name", "model_version", "ontology_version", "generated_at", "input_products"]:
            payload = model_run()
            del payload[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_strings_and_nested_product_metadata_are_required(self):
        for field in ["scenario_id", "run_id", "model_name", "model_version", "ontology_version"]:
            for value in [None, "", " ", 12, []]:
                payload = model_run()
                payload[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.contracts.validate_package(payload)
        for value in [[], {}, ["demo:input"], [{"product_id": "demo:input"}], [{"product_id": "", "version": "1"}]]:
            payload = model_run()
            payload["input_products"] = value
            with self.subTest(products=value), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_nonfinite_bool_and_nonnumeric_results_are_rejected(self):
        for value in [float("nan"), float("inf"), float("-inf"), True, False, "1", None]:
            payload = model_run()
            payload["outputs"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_timestamps_require_an_explicit_timezone(self):
        for timestamp in ["2026-11-13T12:00:00", "2026-11-13", "not-a-date", None, 123]:
            for target in ["generated_at", "valid_time"]:
                payload = model_run()
                if target == "generated_at":
                    payload[target] = timestamp
                else:
                    payload["outputs"][0][target] = timestamp
                with self.subTest(timestamp=timestamp, target=target), self.assertRaises(ValueError):
                    self.contracts.validate_package(payload)

    def test_invalid_or_empty_output_records_are_rejected(self):
        for field in ["entity_id", "metric", "unit", "valid_time", "value"]:
            payload = model_run()
            del payload["outputs"][0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)
        for value in [[], {}, [None], ["code"], [model_run()["outputs"][0]] * 5001]:
            payload = model_run()
            payload["outputs"] = value
            with self.subTest(count=len(value)), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_dependency_evidence_and_open_intervals_are_preserved(self):
        for role in ["declared", "inferred", "simulated"]:
            payload = dependencies()
            payload["evidence_role"] = role
            payload["relationships"][0]["direction"] = "bidirectional"
            result = self.contracts.validate_package(payload)
            self.assertEqual(result["evidence_role"], role)
            self.assertIsNone(result["relationships"][0]["valid_to"])

    def test_invalid_dependency_references_directions_and_intervals_are_rejected(self):
        invalid = [
            ("source_id", ""), ("target_id", "demo:terminal_a"), ("relation_type", ""),
            ("direction", "reverse"), ("evidence_ref", ""), ("valid_from", "2026-11-13T12:00"),
            ("valid_to", "2026-11-13T11:59:59Z"), ("valid_to", "2026-11-13T12:00:00Z"),
        ]
        for field, value in invalid:
            payload = dependencies()
            payload["relationships"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)
        for field in dependencies()["relationships"][0]:
            payload = dependencies()
            del payload["relationships"][0][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_dependencies_require_wp4_and_bounded_nonempty_relationships(self):
        for field, value in [("module_id", "WP3"), ("evidence_role", "verified"), ("dataset_id", ""),
                             ("version", None), ("relationships", []), ("relationships", [None]),
                             ("relationships", [dependencies()["relationships"][0]] * 5001)]:
            payload = dependencies()
            payload[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)

    def test_exact_matching_outputs_compare_b_minus_a_across_scenarios(self):
        left, right = model_run(), model_run()
        right.update(scenario_id="demo:baseline", run_id="demo:run_b")
        right["outputs"][0].update(value=14, valid_time="2026-11-13T14:00:00+01:00")
        result = self.contracts.compare_run_outputs(left, right)
        self.assertEqual(list(result), ["entity_id", "metric", "unit", "valid_time", "value_a", "value_b", "delta", "state"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["delta"], 4)
        self.assertEqual(result.iloc[0]["state"], "Matched")

    def test_unmatched_outputs_stay_visible_without_zero_filling(self):
        for field, value in [("entity_id", "demo:terminal_b"), ("metric", "recovery_time"),
                             ("unit", "hours"), ("valid_time", "2026-11-13T14:00:00Z")]:
            left, right = model_run(), model_run()
            right["outputs"][0][field] = value
            result = self.contracts.compare_run_outputs(left, right)
            with self.subTest(field=field):
                self.assertEqual(set(result["state"]), {"A only", "B only"})
                self.assertTrue(result["delta"].isna().all())
                self.assertTrue(result.loc[result["state"].eq("A only"), "value_b"].isna().all())
                self.assertTrue(result.loc[result["state"].eq("B only"), "value_a"].isna().all())

    def test_integer_deltas_are_exact_beyond_int64_and_float_range(self):
        for value_a, value_b in [(9223372036854775807, -9223372036854775808), (10 ** 400, -(10 ** 400))]:
            left, right = model_run(), model_run()
            left["outputs"][0]["value"] = value_a
            right["outputs"][0]["value"] = value_b
            with self.subTest(value_a=value_a):
                try:
                    result = self.contracts.compare_run_outputs(left, right)
                except ValueError as error:
                    self.fail(f"Finite Python integer values must retain exact arithmetic: {error}")
                self.assertEqual(result.iloc[0]["delta"], value_b - value_a)
                self.assertIsInstance(result.iloc[0]["delta"], int)

    def test_outer_join_preserves_unmatched_integer_precision(self):
        left, right = model_run(), model_run()
        left["outputs"][0]["value"] = 9007199254740993
        right["outputs"][0]["entity_id"] = "demo:terminal_b"
        result = self.contracts.compare_run_outputs(left, right)
        unmatched = result.loc[result["state"].eq("A only")].iloc[0]
        self.assertEqual(unmatched["value_a"], 9007199254740993)
        self.assertIsInstance(unmatched["value_a"], int)
        self.assertTrue(pd.isna(unmatched["value_b"]))
        self.assertTrue(pd.isna(unmatched["delta"]))

    def test_nonfinite_float_delta_is_rejected(self):
        left, right = model_run(), model_run()
        left["outputs"][0]["value"] = 1e308
        right["outputs"][0]["value"] = -1e308
        with self.assertRaisesRegex(ValueError, "finite"):
            self.contracts.compare_run_outputs(left, right)

    def test_duplicate_keys_and_different_ontologies_cannot_be_compared(self):
        left, right = model_run(), model_run()
        duplicate = deepcopy(left["outputs"][0])
        duplicate["valid_time"] = "2026-11-13T14:00:00+01:00"
        left["outputs"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "[Dd]uplicate"):
            self.contracts.compare_run_outputs(left, right)
        right["ontology_version"] = "another-ontology"
        with self.assertRaisesRegex(ValueError, "ontology"):
            self.contracts.compare_run_outputs(model_run(), right)
        with self.assertRaisesRegex(ValueError, "model_run"):
            self.contracts.compare_run_outputs(model_run(), dependencies())

    def test_templates_are_illustrative_valid_packages_and_independent_copies(self):
        for kind in ["model_run", "dependencies"]:
            template = self.contracts.package_template(kind)
            self.assertEqual(template["notes"], "Illustrative integration template, not a CRDT result")
            self.assertEqual(self.contracts.validate_package(template)["artifact_type"], kind)
            if kind == "model_run":
                self.assertEqual(template["outputs"][0]["entity_id"], "demo:terminal_a")
            template["notes"] = "changed"
            self.assertNotEqual(self.contracts.package_template(kind)["notes"], "changed")
        with self.assertRaises(ValueError):
            self.contracts.package_template("code")

    def test_nonobject_packages_and_nontext_notes_are_rejected(self):
        for payload in [None, [], "print('example')"]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.contracts.validate_package(payload)
        payload = model_run()
        payload["notes"] = {"url": "https://example.invalid/code.py"}
        with self.assertRaises(ValueError):
            self.contracts.validate_package(payload)


if __name__ == "__main__":
    unittest.main()
