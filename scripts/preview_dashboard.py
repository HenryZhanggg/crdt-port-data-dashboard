"""Local UI verification with captured observations; not a deployment entry point."""
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from api_connectors import empty_bundle, status_row

bundle = empty_bundle()
snapshot = BASE / "outputs" / "2026-10-06" / "live_water.json"
if snapshot.exists():
    bundle["water_levels"] = pd.read_json(snapshot)
    bundle["water_levels"]["date_time"] = pd.to_datetime(bundle["water_levels"]["date_time"], utc=True)
for name, filename, time_column in [
    ("webtris_sites", "raw_webtris_sites_liverpool.csv", None),
    ("webtris_daily", "raw_webtris_daily_a5036.csv", "timestamp"),
    ("weekly_shipping", "raw_ons_weekly_shipping_liverpool.csv", "week_ending"),
]:
    path = BASE / "data" / filename
    if path.exists():
        bundle[name] = pd.read_csv(path)
        if time_column in bundle[name]:
            bundle[name][time_column] = pd.to_datetime(bundle[name][time_column], errors="coerce")
bundle["status"] = pd.DataFrame([status_row("ea_liverpool_tide_water_level_api", "EA captured observations", "Water Level", "snapshot_loaded", len(bundle["water_levels"]), "https://environment.data.gov.uk/flood-monitoring", "Captured snapshot for local UI verification")])
st.session_state["dashboard_authorised"] = True
with patch("api_connectors.fetch_raw_data_bundle", return_value=bundle):
    runpy.run_path(str(BASE / "app.py"), run_name="__main__")
st.caption("LOCAL QA PREVIEW: water is a captured EA observation snapshot; traffic and shipping use saved historical tables. This preview does not refresh these sources.")
