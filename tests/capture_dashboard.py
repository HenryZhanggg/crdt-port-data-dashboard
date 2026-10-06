"""Capture the running local preview and check navigation and mobile overflow."""
import json
import math
from pathlib import Path
import zipfile

import pandas as pd

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "2026-10-06"
OUTPUT.mkdir(parents=True, exist_ok=True)
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="chrome", headless=True, args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader"])
    page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8515", wait_until="domcontentloaded")
    page.get_by_text("Liverpool monitoring and data quality", exact=True).wait_for(timeout=45000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
    page.locator('[data-testid="stPlotlyChart"]').first.wait_for()
    page.locator('[data-testid="stDeckGlJsonChart"]').first.wait_for()
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUTPUT / "workspace_overview_desktop.png"), full_page=True)
    results.append({"page": "Overview", "exceptions": page.locator('[data-testid="stException"]').count()})
    water = pd.read_json(OUTPUT / "live_water.json")
    row = water[water["station_reference"].eq("E70139")].iloc[0]
    canvas = page.locator('[data-testid="stDeckGlJsonChart"] canvas').first
    bounds = canvas.bounding_box()
    scale = 512 * 2 ** 11.5
    def mercator(lat):
        sine = math.sin(math.radians(lat))
        return 0.5 - math.log((1 + sine) / (1 - sine)) / (4 * math.pi)
    x = bounds["x"] + bounds["width"] / 2 + (row["lon"] + 3.015) / 360 * scale
    y = bounds["y"] + bounds["height"] / 2 + (mercator(row["lat"]) - mercator(53.448)) * scale
    page.mouse.click(x, y)
    page.get_by_text("E70139 / WATER LEVEL", exact=True).wait_for(timeout=20000)
    results.append({"page": "Map point selection", "selected_station": "E70139"})
    for name, ready, filename in [
        ("Observation Explorer", "Download selected observations", "workspace_water_desktop.png"),
        ("Data Quality", "Download observation graph (Turtle)", "workspace_quality_desktop.png"),
        ("GIS", "Monitoring location", "workspace_map_desktop.png"),
    ]:
        page.get_by_text(name, exact=True).click()
        page.get_by_text(ready, exact=True).wait_for(timeout=20000)
        page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUTPUT / filename), full_page=True)
        results.append({"page": name, "exceptions": page.locator('[data-testid="stException"]').count()})
    page.get_by_text("Data & Research", exact=True).click()
    page.get_by_text("Research & Replay", exact=True).click()
    page.get_by_text("Replay checkpoint", exact=True).wait_for(timeout=20000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUTPUT / "workspace_replay_desktop.png"), full_page=True)
    results.append({"page": "Historical replay", "exceptions": page.locator('[data-testid="stException"]').count()})
    page.get_by_role("tab", name="Experiment evidence", exact=True).click()
    page.get_by_text("Feature families", exact=True).wait_for()
    page.screenshot(path=str(OUTPUT / "workspace_evidence_desktop.png"), full_page=True)
    results.append({"page": "Experiment evidence", "exceptions": page.locator('[data-testid="stException"]').count()})
    page.get_by_text("Report Centre", exact=True).click()
    page.get_by_role("button", name="Download observation report ZIP").wait_for(timeout=20000)
    with page.expect_download() as download:
        page.get_by_role("button", name="Download observation report ZIP").click()
    path = OUTPUT / "verified_observation_report.zip"
    download.value.save_as(path)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert "report.html" in archive.namelist()
    page.screenshot(path=str(OUTPUT / "workspace_report_desktop.png"), full_page=True)
    results.append({"page": "Report download", "zip_integrity": True, "exceptions": page.locator('[data-testid="stException"]').count()})
    page.close()
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8515", wait_until="domcontentloaded")
    page.get_by_text("Liverpool monitoring and data quality", exact=True).wait_for(timeout=45000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUTPUT / "workspace_overview_mobile.png"), full_page=True)
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
    results.append({"page": "Mobile overview", "horizontal_overflow": overflow})
    browser.close()
assert all(item.get("exceptions", 0) == 0 and not item.get("horizontal_overflow", False) for item in results), results
(OUTPUT / "workspace_browser_checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results))
