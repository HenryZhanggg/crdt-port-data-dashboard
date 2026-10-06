"""Capture the running local preview and check navigation and mobile overflow."""
import json
from pathlib import Path

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
    page.screenshot(path=str(OUTPUT / "overview_desktop.png"), full_page=True)
    results.append({"page": "Overview", "exceptions": page.locator('[data-testid="stException"]').count()})
    for name, ready, filename in [
        ("Weather", "Water-level observations", "water_desktop.png"),
        ("Data Quality", "Data quality and compatibility", "quality_desktop.png"),
        ("GIS", "Monitoring map", "map_desktop.png"),
    ]:
        page.get_by_text(name, exact=True).click()
        page.get_by_text(ready, exact=True).wait_for(timeout=20000)
        page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUTPUT / filename), full_page=True)
        results.append({"page": name, "exceptions": page.locator('[data-testid="stException"]').count()})
    page.close()
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8515", wait_until="domcontentloaded")
    page.get_by_text("Liverpool monitoring and data quality", exact=True).wait_for(timeout=45000)
    page.get_by_text("Stop", exact=True).wait_for(state="hidden", timeout=45000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUTPUT / "overview_mobile.png"), full_page=True)
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
    results.append({"page": "Mobile overview", "horizontal_overflow": overflow})
    browser.close()
assert all(item.get("exceptions", 0) == 0 and not item.get("horizontal_overflow", False) for item in results), results
(OUTPUT / "browser_checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results))
