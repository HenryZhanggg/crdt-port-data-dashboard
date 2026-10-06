# Monitoring and Research Workspace Implementation Plan

> Execute inline with the executing-plans and test-driven-development skills. The user approved the six-module scope on 6 October 2026; monitoring remains the default home.

**Goal:** A professional monitoring workspace with selectable map stations, observation exploration, actionable data-health evidence, eight-observation replay, verified research results and portable reports.

**Architecture:** Preserve Streamlit, existing access checks, source catalogue and the blue/teal theme. Add pure observation/report helpers in `workspace_data.py` and research/report views in `research_views.py`; update existing monitoring views and load only the feeds needed by each page. Reuse the existing GitHub deployment checkout for the final verified commit; do not publish secrets, raw research predictions or caches.

**Tech Stack:** Existing Streamlit, pandas, Plotly, pydeck, RDFLib/pySHACL, unittest and Playwright. No new runtime dependencies.

## 1. Data and Reports

- [x] Add `tests/test_workspace_data.py`, then run `.venv/Scripts/python.exe -m unittest discover -s tests -p test_workspace_data.py -v` and confirm missing functionality fails.
- [x] Implement `clean_water_series(frame)` for one gauge/datum only, UTC timestamps, invalid/missing values and duplicate removal. `rate_per_hour` is calculated only across consecutive 15-minute observations; missing intervals remain gaps.
- [x] Implement `window_features(window)` and `quality_findings(table)`. A complete window needs eight finite observations spaced exactly 15 minutes apart; its span is 105 minutes. No future observations, imputation, datum conversion or risk inference.
- [x] Implement `report_archive(bundle, table, start, end)` with a self-contained HTML snapshot, separate charts per measurement reference, CSV files and a metadata JSON. Escape source strings and record observation/collection/export times distinctly.
- [x] Repeat helper tests and compile source.

## 2. Source Loading

- [x] Add connector tests for `fetch_raw_data_bundle(..., sources=("water_level",))`: no other feed is requested, and a failed selected feed becomes an explicit status row.
- [x] Add the optional `sources` parameter to the existing connector dispatcher. Cache observation feeds for five minutes and statistical/reference feeds for one day, independently. Keep full-feed loading for Raw Data, Catalogue and Data Status.
- [x] Adapt the existing AppTest fixture patch and add assertions that observation/replay pages do not request shipping or traffic. Quality rows must not represent an unrequested statistical feed as unavailable.

## 3. Monitoring UI

- [x] Update `app.py` navigation into Monitoring and Data & Research groups; rename Weather to Observation Explorer and retain the other existing views.
- [x] Refine the overview into a map-led workspace, latest single-reference water trend, compact metadata and correct stale/partial/empty states. No flood-risk status is inferred.
- [x] Use stable deck layer IDs and `on_select="rerun"` to show the selected water gauge or traffic counter. A station selector is also available when WebGL is unavailable. Never imply that demonstration assets are operational assets.
- [x] Add observation range filtering, rate-of-change panels, CSV export and gap markers. Extend Data Quality with prioritized findings while retaining SHACL and Turtle export.

## 4. Research and Replay

- [x] Extract `Summary_By_Group` and `PerFold_Metrics` from `16_final_context_physics_signature.xlsx` into small public CSVs with a source SHA-256 manifest; check grouped means and standard deviations against the original report. Do not upload the full research workbook or predictions.
- [x] Add `Research & Replay` tabs for a selected-series replay, eight-point window diagnostics and descriptive four-fold result/error-bar charts. Slider and Plotly playback use observed data only. Replay and archived model results remain separate and labelled.
- [x] Explain AP, validation-threshold F2, event recall and false-positive windows per represented day. Fold SD is not a confidence interval; four clusters are not strong population-level evidence.

## 5. Report Centre and Verification

- [x] Add a Report Centre page with selected-period scope, data-quality summary and downloadable ZIP. Tests inspect CSV row counts, HTML escaping, timestamp metadata and independent-reference charts.
- [x] Extend AppTest coverage to every page, empty feeds, historical dates, replay endpoint/filter changes and restricted partner navigation. Run `.venv/Scripts/python.exe -m unittest discover -s tests -v` and compileall.
- [x] Update local snapshot preview and Playwright capture checks. Verify desktop and 390-pixel mobile layouts, actual map selection, replay interaction and report download; inspect screenshots.
- [ ] Update README/release inputs; verify no credentials/caches in the source package. Copy only approved release files into the clean deployment checkout, inspect the diff, commit and push without force.
- [ ] Verify the remote commit and the embedded Streamlit cloud pages, including completed SHACL validation, research plots and report controls. Record the actual deployment outcome.

## Success Criteria

All six approved areas are available. Real, stale, unavailable, sample and offline-research states are distinguishable. Slow unrelated feeds do not block observation pages. Replay never uses future samples or crosses measurement references. Tests, mobile/browser checks and the public source commit are verified before claiming completion.

## Pre-publication Verification Record

6 October 2026: 37 unit/AppTest tests passed; compileall passed. Nine isolated-browser checks passed, including actual map selection, report ZIP integrity and 390-pixel mobile overflow. Independent review findings were reproduced in failing tests and fixed: replay navigation restriction, conflicting duplicate values, displayed-reference freshness, bulk gap shading and preservation of off-cadence observations. A seven-day gapped chart with 335 rectangles was constructed in 0.679 seconds on this computer (not an inference benchmark).

Publication and cloud verification are the final gates; their actual outcome is recorded separately in the deployment receipt, not inferred from this source package.
