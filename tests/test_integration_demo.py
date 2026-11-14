import importlib
import json
import unittest
from copy import deepcopy


class IntegrationDemoTests(unittest.TestCase):
    def setUp(self):
        try:
            self.demo = importlib.import_module("integration_demo")
        except ModuleNotFoundError as error:
            self.fail(f"The illustrative connection checks must be implemented: {error}")

    def connection(self, case="aligned"):
        return self.demo.get_demo_connection(case)

    def checks(self, connection):
        return {row["check"]: row for row in self.demo.check_connection(connection)}

    def test_cases_are_explicit_demo_drafts_and_independent_copies(self):
        self.assertEqual(set(self.demo.DEMO_CASES), {
            "shared_view", "aligned", "missing_input", "missing_baseline",
            "reference_mismatch", "time_mismatch", "dynamic_feedback",
        })
        for case in self.demo.DEMO_CASES:
            connection = self.connection(case)
            self.assertEqual(connection["status"], "DEMO DRAFT")
            self.assertTrue(connection["connection_id"].startswith("demo:"))
            self.assertIn("not a CRDT result", connection["notes"])
            for side in ["source", "target"]:
                self.assertTrue(connection[side]["model_id"].startswith("demo:"))
                self.assertIn("unapproved", connection[side]["ontology_version"])
            connection["source"]["value"] = 123
            self.assertNotEqual(self.connection(case)["source"]["value"], 123)
        with self.assertRaises(ValueError):
            self.connection("does_not_exist")

    def test_aligned_metadata_passes_technical_checks_but_acceptance_is_pending(self):
        checks = self.checks(self.connection())
        self.assertFalse(any(row["status"] == "Blocked" for row in checks.values()))
        self.assertEqual(checks["Provider and consumer acceptance"]["status"], "Review")
        self.assertIn("Pending", checks["Provider and consumer acceptance"]["detail"])
        for row in checks.values():
            self.assertEqual(set(row), {"check", "status", "detail", "owner"})
            self.assertTrue(row["owner"])
            self.assertTrue(row["detail"])

    def test_checker_does_not_mutate_the_connection(self):
        connection = self.connection()
        before = deepcopy(connection)
        self.demo.execution_preview(connection, self.demo.check_connection(connection))
        self.assertEqual(connection, before)

    def test_absent_invalid_and_nonfinite_ratios_block_downstream_without_zero_fill(self):
        for value in [None, "0.8", True, False, float("nan"), float("inf"), -0.01, 1.01]:
            with self.subTest(value=value):
                connection = self.connection()
                connection["source"]["value"] = value
                rows = self.checks(connection)
                self.assertEqual(rows["Provider value"]["status"], "Blocked")
                preview = self.demo.execution_preview(connection, list(rows.values()))
                self.assertTrue(all(row["status"] == "Blocked" for row in preview[1:]))
                self.assertNotIn("0 t/h", " ".join(row["reason"] for row in preview))

    def test_zero_and_one_are_valid_ratios_and_preserved_as_real_values(self):
        for value, output in [(0, "0 t/h"), (1, "1000 t/h")]:
            connection = self.connection()
            connection["source"]["value"] = value
            rows = self.demo.check_connection(connection)
            self.assertEqual(self.checks(connection)["Provider value"]["status"], "Pass")
            self.assertIn(output, self.demo.execution_preview(connection, rows)[1]["reason"])

    def test_missing_baseline_and_invalid_baseline_values_block_adapter(self):
        for baseline in [None, {}, {"value": None}, {"value": -1}, {"value": True},
                         {"value": float("inf")}, {"value": "1000"}]:
            connection = self.connection()
            connection["baseline"] = baseline
            rows = self.demo.check_connection(connection)
            self.assertEqual(self.checks(connection)["Baseline capacity"]["status"], "Blocked")
            self.assertEqual(self.demo.execution_preview(connection, rows)[1]["status"], "Blocked")

    def test_ratio_cannot_be_relabelled_as_capacity_without_the_fixed_declared_adapter(self):
        mutations = [("declared", False), ("id", "arbitrary"),
                     ("expression", "__import__('os').system('bad')")]
        for field, value in mutations:
            connection = self.connection()
            connection["adapter"][field] = value
            with self.subTest(field=field):
                self.assertEqual(self.checks(connection)["Declared adapter"]["status"], "Blocked")
        for side, variable in [("source", "capacity"), ("target", "availability_ratio")]:
            connection = self.connection()
            connection[side]["variable"] = variable
            self.assertEqual(self.checks(connection)["Declared adapter"]["status"], "Blocked")

    def test_incompatible_units_block_even_with_a_numeric_baseline(self):
        for side, unit in [("source", "%"), ("target", "TEU/day"), ("baseline", "TEU/day")]:
            connection = self.connection()
            connection[side]["unit"] = unit
            with self.subTest(side=side):
                self.assertEqual(self.checks(connection)["Units"]["status"], "Blocked")

    def test_equal_units_do_not_hide_a_different_or_missing_baseline_reference(self):
        for side in ["source", "target", "baseline"]:
            for value in ["demo:another_nominal_capacity", ""]:
                connection = self.connection()
                connection[side]["reference"] = value
                with self.subTest(side=side, value=value):
                    self.assertEqual(self.checks(connection)["Capacity reference"]["status"], "Blocked")

    def test_context_checks_require_matching_nonempty_metadata(self):
        labels = {"entity_id": "Entity identity", "ontology_version": "Ontology version",
                  "scenario_id": "Scenario", "spatial_scope": "Spatial scope", "time_basis": "Time basis"}
        for field, label in labels.items():
            for value in ["different", "", None]:
                connection = self.connection()
                connection["target"][field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.checks(connection)[label]["status"], "Blocked")
            connection = self.connection()
            connection["source"][field] = connection["target"][field] = ""
            self.assertEqual(self.checks(connection)[label]["status"], "Blocked")

    def test_model_identity_version_wp_and_evidence_are_required_on_both_sides(self):
        for side in ["source", "target"]:
            for field in ["model_id", "version", "wp", "evidence_ref"]:
                connection = self.connection()
                del connection[side][field]
                with self.subTest(side=side, field=field):
                    self.assertEqual(self.checks(connection)["Model provenance"]["status"], "Blocked")
        connection = self.connection()
        connection["baseline"]["evidence_ref"] = ""
        self.assertEqual(self.checks(connection)["Baseline capacity"]["status"], "Blocked")

    def test_pending_or_claimed_acceptance_never_becomes_scientific_approval(self):
        for acceptance in [{}, {"provider": "Approved", "consumer": "Approved"}]:
            connection = self.connection()
            connection["acceptance"] = acceptance
            self.assertEqual(self.checks(connection)["Provider and consumer acceptance"]["status"], "Review")
            preview = self.demo.execution_preview(connection, self.demo.check_connection(connection))
            self.assertEqual(preview[2]["status"], "Review")
            self.assertEqual(preview[-1]["status"], "Blocked")

    def test_fixtures_explain_their_specific_failure(self):
        expected = {"missing_input": "Provider value", "missing_baseline": "Baseline capacity",
                    "reference_mismatch": "Capacity reference", "time_mismatch": "Time basis",
                    "dynamic_feedback": "Connection mode"}
        for case, label in expected.items():
            with self.subTest(case=case):
                self.assertEqual(self.checks(self.connection(case))[label]["status"], "Blocked")

    def test_aligned_preview_computes_only_an_illustrative_adapter_result(self):
        connection = self.connection()
        preview = self.demo.execution_preview(connection, self.demo.check_connection(connection))
        self.assertEqual([row["status"] for row in preview], ["Pass", "Pass", "Review", "Blocked"])
        self.assertIn("800 t/h", preview[1]["reason"])
        self.assertIn("illustrative", preview[1]["reason"].lower())
        self.assertIn("not connected", preview[-1]["reason"])
        for row in preview:
            self.assertEqual(set(row), {"stage", "owner", "status", "reason"})

    def test_shared_view_has_no_adapter_or_automatic_model_chain(self):
        connection = self.connection("shared_view")
        checks = self.demo.check_connection(connection)
        self.assertEqual(connection["mode"], "view_only")
        self.assertFalse(connection["adapter"]["declared"])
        self.assertEqual(self.checks(connection)["Connection mode"]["status"], "Review")
        self.assertEqual(self.checks(connection)["Declared adapter"]["status"], "Review")
        preview = self.demo.execution_preview(connection, checks)
        self.assertTrue(all(row["status"] != "Pass" for row in preview[1:]))
        self.assertIn("shared", " ".join(row["reason"] for row in preview).lower())

    def test_dynamic_feedback_is_blocked_until_explicit_design_agreement(self):
        connection = self.connection("dynamic_feedback")
        rows = self.demo.check_connection(connection)
        detail = self.checks(connection)["Connection mode"]["detail"].lower()
        for requirement in ["time step", "feedback", "convergence", "failure"]:
            self.assertIn(requirement, detail)
        preview = self.demo.execution_preview(connection, rows)
        self.assertTrue(all(row["status"] == "Blocked" for row in preview[1:]))

    def test_empty_or_unknown_modes_do_not_allow_a_handover(self):
        for mode in [None, "", "live"]:
            connection = self.connection()
            connection["mode"] = mode
            self.assertEqual(self.checks(connection)["Connection mode"]["status"], "Blocked")

    def test_summary_distinguishes_technical_readiness_from_execution_and_approval(self):
        summary = self.demo.connection_summary(self.demo.check_connection(self.connection()))
        for word in ["technical", "acceptance", "not connected"]:
            self.assertIn(word, summary.lower())
        blocked = self.demo.connection_summary(self.demo.check_connection(self.connection("missing_input")))
        self.assertIn("Blocked", blocked)
        self.assertIn("Provider value", blocked)
        shared = self.demo.connection_summary(self.demo.check_connection(self.connection("shared_view")))
        self.assertIn("shared", shared.lower())
        self.assertNotIn("ready", shared.lower())

    def test_empty_check_list_cannot_indicate_readiness(self):
        self.assertIn("Blocked", self.demo.connection_summary([]))
        preview = self.demo.execution_preview(self.connection(), [])
        self.assertTrue(all(row["status"] == "Blocked" for row in preview[1:]))

    def test_handover_template_is_a_serializable_draft_with_empty_partner_fields(self):
        template = self.demo.get_handover_template()
        self.assertEqual(template["status"], "DRAFT - partner completion required")
        for side in ["source", "target"]:
            for field in ["model_id", "version", "wp", "entity_id", "ontology_version", "evidence_ref"]:
                self.assertEqual(template[side][field], "")
        self.assertIsNone(template["source"]["value"])
        self.assertIsNone(template["baseline"]["value"])
        self.assertFalse(template["adapter"]["declared"])
        self.assertEqual(template["acceptance"], {"provider": "Pending", "consumer": "Pending"})
        json.dumps(template, allow_nan=False)
        template["source"]["model_id"] = "changed"
        self.assertEqual(self.demo.get_handover_template()["source"]["model_id"], "")

    def test_partner_template_covers_handover_agreements_without_the_demo_adapter(self):
        template = self.demo.get_handover_template()
        self.assertEqual(template["adapter"], {"id": "", "expression": "", "declared": False})
        expected_sections = {
            "responsible_contacts": {"provider", "consumer"},
            "purpose": {"intended_use", "decision_context"},
            "data_requirements": {"required_inputs", "expected_outputs", "temporal_resolution", "spatial_resolution"},
            "quality_policy": {"quality_criteria", "missing_data_policy", "error_handling"},
            "access_use_terms": {"access_method", "licence", "use_terms", "restrictions"},
            "verification_acceptance": {"verification_method", "acceptance_criteria", "provider_status", "consumer_status"},
            "execution_requirements": {"trigger", "sequence", "interface", "failure_policy"},
            "provenance_versions": {"input_versions", "model_versions", "adapter_version", "review_record"},
        }
        for section, fields in expected_sections.items():
            with self.subTest(section=section):
                self.assertEqual(set(template[section]), fields)
        for side in ["provider", "consumer"]:
            self.assertEqual(template["responsible_contacts"][side], {"name": "", "organization": "", "contact": ""})
            self.assertEqual(template["verification_acceptance"][f"{side}_status"], "Pending")
        for section, record in template.items():
            if section in expected_sections and section != "responsible_contacts":
                for field, value in record.items():
                    if field not in ["provider_status", "consumer_status"]:
                        self.assertIn(value, ["", []], (section, field))
        template["data_requirements"]["required_inputs"].append("changed")
        self.assertEqual(self.demo.get_handover_template()["data_requirements"]["required_inputs"], [])


if __name__ == "__main__":
    unittest.main()
