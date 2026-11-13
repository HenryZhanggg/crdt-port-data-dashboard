import unittest

import pandas as pd

from workbench_data import build_entities, choose_entity, selected_water


def water_rows():
    now = pd.Timestamp.now(tz="UTC").floor("min")
    base = {"station_reference": "E70139", "station_label": "Liverpool", "value": 1.2,
            "unit": "mAOD", "datum": "Ordnance Datum Newlyn", "datum_uri": "datum:a",
            "lat": 53.448, "lon": -3.015, "api_endpoint": "https://example.org/readings"}
    return pd.DataFrame([
        dict(base, date_time=now - pd.Timedelta(minutes=15)),
        dict(base, date_time=now),
        dict(base, date_time=now - pd.Timedelta(days=1), datum="Local datum", datum_uri="datum:b"),
        dict(base, date_time="invalid", unit="m", datum="Local datum", datum_uri="datum:b"),
    ])


class WorkbenchDataTests(unittest.TestCase):
    def test_water_identity_uses_latest_valid_measurement_reference(self):
        water = water_rows()
        entity = build_entities({"water_levels": water}).iloc[0]
        self.assertEqual(entity["entity_id"], "water:E70139")
        self.assertEqual(entity["kind"], "Water")
        self.assertEqual(entity["evidence_role"], "Observed")
        self.assertEqual(entity["station_reference"], "E70139")
        self.assertEqual(entity["unit"], "mAOD")
        self.assertEqual(entity["datum_uri"], "datum:a")
        self.assertEqual(entity["datum"], "Ordnance Datum Newlyn")
        self.assertEqual(entity["state"], "Current")
        self.assertEqual(entity["latest_time"], water.iloc[1]["date_time"])
        self.assertEqual(entity["source_url"], "https://example.org/readings")

    def test_water_selection_returns_only_the_exact_raw_reference(self):
        water = water_rows()
        other_station = water.iloc[[0]].assign(station_reference="E70124")
        bundle = {"water_levels": pd.concat([water, other_station])}
        entity = build_entities(bundle).iloc[0].to_dict()
        actual = selected_water(bundle, entity)
        pd.testing.assert_frame_equal(actual, water.iloc[:2])
        self.assertNotIn("rate_per_hour", actual)

    def test_water_identity_stays_stable_when_displayed_reference_changes(self):
        bundle = {"water_levels": water_rows()}
        original = build_entities(bundle).iloc[0]
        newer = water_rows().iloc[[1]].assign(unit="m", datum="Local datum", datum_uri="datum:b")
        newer["date_time"] += pd.Timedelta(minutes=1)
        bundle["water_levels"] = pd.concat([bundle["water_levels"], newer])
        changed = build_entities(bundle).iloc[0]
        self.assertEqual(changed["entity_id"], original["entity_id"])
        self.assertEqual(changed["unit"], "m")
        self.assertEqual(changed["datum_uri"], "datum:b")

    def test_missing_datum_remains_empty_and_selectable(self):
        water = water_rows().iloc[:2].assign(datum=None, datum_uri=float("nan"))
        bundle = {"water_levels": water}
        entity = build_entities(bundle).iloc[0].to_dict()
        self.assertEqual(entity["datum_uri"], "")
        self.assertEqual(entity["datum"], "")
        pd.testing.assert_frame_equal(selected_water(bundle, entity), water)

    def test_invalid_water_times_retain_a_station_with_unknown_time(self):
        water = water_rows().iloc[[0]].assign(date_time="invalid")
        entity = build_entities({"water_levels": water}).iloc[0]
        self.assertEqual(entity["state"], "Unknown time")
        self.assertTrue(pd.isna(entity["latest_time"]))

    def test_traffic_without_observations_is_a_reference_location(self):
        bundle = {"webtris_sites": pd.DataFrame([
            {"site_id": "6806", "description": "A5036 counter", "lat": 53.459, "lon": -2.999},
            {"site_id": "6806", "description": "Duplicate counter", "lat": 53.459, "lon": -2.999},
        ])}
        entities = build_entities(bundle)
        self.assertEqual(len(entities), 1)
        entity = entities.iloc[0]
        self.assertEqual(entity["entity_id"], "traffic:6806")
        self.assertEqual(entity["kind"], "Traffic")
        self.assertEqual(entity["evidence_role"], "Reference")
        self.assertEqual(entity["state"], "Reference location")
        self.assertEqual(entity["site_id"], "6806")
        self.assertTrue(pd.isna(entity["latest_time"]))

    def test_traffic_observation_quality_is_per_site(self):
        now = pd.Timestamp.now(tz="UTC").floor("min")
        bundle = {"webtris_sites": pd.DataFrame([
            {"site_id": "6806"}, {"site_id": "6807"}, {"site_id": "6808"}]),
            "webtris_daily": pd.DataFrame([
                {"site_id": "6806", "timestamp": now, "Total Volume": 10},
                {"site_id": "6807", "timestamp": now - pd.Timedelta(days=1), "Total Volume": 20},
            ])}
        entities = build_entities(bundle).set_index("entity_id")
        self.assertEqual(entities.loc["traffic:6806", "state"], "Current")
        self.assertEqual(entities.loc["traffic:6807", "state"], "Stale")
        self.assertEqual(entities.loc["traffic:6806", "evidence_role"], "Observed")
        self.assertEqual(entities.loc["traffic:6808", "state"], "Reference location")

    def test_naive_traffic_timestamp_does_not_claim_verified_freshness(self):
        bundle = {"webtris_sites": pd.DataFrame([{"site_id": "6806"}]),
                  "webtris_daily": pd.DataFrame([{"site_id": "6806", "timestamp": pd.Timestamp.now(), "Total Volume": 10}])}
        entity = build_entities(bundle).iloc[0]
        self.assertEqual(entity["state"], "Timezone unverified")
        self.assertTrue(pd.isna(entity["latest_time"]))

    def test_traffic_ids_match_after_a_merge_promotes_integer_ids_to_float(self):
        bundle = {"webtris_sites": pd.DataFrame([{"site_id": 6806}]),
                  "webtris_daily": pd.DataFrame([
                      {"site_id": 6806, "timestamp": pd.Timestamp.now(tz="UTC")},
                      {"site_id": None, "timestamp": pd.Timestamp.now(tz="UTC")},
                  ])}
        entity = build_entities(bundle).iloc[0]
        self.assertEqual(entity["entity_id"], "traffic:6806")
        self.assertEqual(entity["state"], "Current")

    def test_demo_assets_are_opt_in_samples_regardless_of_csv_status(self):
        assets = pd.DataFrame([{"asset_id": "gate_north", "name": "North gate", "status": "Warning", "lat": 53.4, "lon": -3}])
        self.assertTrue(build_entities({}, assets).empty)
        entity = build_entities({}, assets, include_demo=True).iloc[0]
        self.assertEqual(entity["entity_id"], "demo:gate_north")
        self.assertEqual(entity["kind"], "Demonstration")
        self.assertEqual(entity["evidence_role"], "Illustrative")
        self.assertEqual(entity["state"], "Sample")

    def test_invalid_coordinates_stay_in_the_registry_as_nan(self):
        water = water_rows().iloc[[1]].assign(lat="invalid", lon=float("inf"))
        sites = pd.DataFrame([{"site_id": "6806", "lat": 91, "lon": -181}])
        assets = pd.DataFrame([{"asset_id": "gate", "name": "Gate", "lat": None, "lon": "invalid"}])
        entities = build_entities({"water_levels": water, "webtris_sites": sites}, assets, include_demo=True)
        self.assertEqual(len(entities), 3)
        self.assertTrue(entities[["lat", "lon"]].isna().all().all())

    def test_empty_registry_has_the_public_columns(self):
        entities = build_entities({})
        self.assertTrue(entities.empty)
        self.assertTrue({"entity_id", "name", "kind", "evidence_role", "state", "lat", "lon", "station_reference",
                         "unit", "datum", "datum_uri", "site_id", "source_url", "latest_time"}.issubset(entities.columns))

    def test_empty_demo_table_does_not_require_asset_columns(self):
        self.assertTrue(build_entities({}, pd.DataFrame(), include_demo=True).empty)

    def test_nonwater_and_empty_selections_return_empty_frames(self):
        bundle = {"water_levels": water_rows()}
        self.assertTrue(selected_water(bundle, {"kind": "Traffic", "site_id": "6806"}).empty)
        self.assertTrue(selected_water({}, {"kind": "Water", "station_reference": "E70139"}).empty)
        self.assertTrue(selected_water(bundle, {}).empty)

    def test_new_valid_map_click_changes_selection(self):
        entities = pd.DataFrame({"entity_id": ["water:A", "traffic:B"]})
        self.assertEqual(choose_entity(entities, "water:A", "traffic:B", "water:A"), "traffic:B")

    def test_unchanged_map_click_preserves_the_newer_manual_selection(self):
        entities = pd.DataFrame({"entity_id": ["water:A", "traffic:B"]})
        self.assertEqual(choose_entity(entities, "traffic:B", "water:A", "water:A"), "traffic:B")

    def test_invalid_map_click_does_not_replace_valid_selection(self):
        entities = pd.DataFrame({"entity_id": ["water:A", "traffic:B"]})
        self.assertEqual(choose_entity(entities, "traffic:B", "demo:hidden"), "traffic:B")

    def test_hidden_or_removed_selection_falls_back_to_a_visible_entity(self):
        entities = pd.DataFrame({"entity_id": ["water:A", "traffic:B"]})
        self.assertEqual(choose_entity(entities, "demo:hidden", "demo:hidden"), "water:A")
        self.assertIsNone(choose_entity(pd.DataFrame(), "water:A", "water:A"))


if __name__ == "__main__":
    unittest.main()
