# CRDT port dashboard version 1

The version 1 interface uses compact white engineering panels, a navy maritime map and relationship view, shorter object-navigation labels, and a shared object inspector. Browser, login, sidebar, application header and inner page heading use the same display name. Selected-object links are emphasized, with a textual legend and labeled identity/time/evidence fields. Illustrative-data labels and full identities/provenance remain available throughout the semantic workspace.

This repository contains an ontology-guided home demonstration and a separate live-monitoring workbench for CRDT-Port. The default Overview uses a local RDF vocabulary, typed fictional objects, declared relationships and synthetic products to demonstrate semantic navigation and linked views. Live Monitoring retains real-source observation, quality and SOSA/SHACL inspection. Executable partner models and formal WP1 ontology alignment remain pending.

## Modular port workbench (13 November 2026)

Live Monitoring combines a map, a shared water/traffic/illustrative-asset inspector and selectable panels. Use the top shortcuts for monitoring, objects/dependencies, scenario results, data/evidence and WP handovers; the sidebar retains all existing observation, transport, quality, research/replay, catalogue and report views. The shared observation dates retain their original seven-calendar-day limit. Map colours describe data state, not hazard severity. Demonstration assets and the service-area outline are opt-in.

The 14 November interface refresh adds a compact navy header, time/date/refresh toolbar, source-reference metadata and consistent neutral panels/charts. Existing summary metrics sit above the map; the selected-observation chart sits directly below it. Expand **Workspace panels** to change the optional panels. On narrow screens, the map and trend stack before the object inspector. **Recent observations** requests yesterday and today with cached responses; refresh is manual, not continuous polling.

The maritime-map update uses an authored navy OpenFreeMap basemap in both Live Monitoring and GIS. Cyan marks current water data, amber other water states, blue traffic and grey illustrative assets. Pickable labels separate co-located objects using screen-pixel offsets without changing their source coordinates. Live Monitoring adds a white selection ring and selected-label border linked to the inspector. Native map selection resets when visible membership or the manual object choice changes; this also resets the camera, avoiding stale row-index selection. The map shows geographic context, not surveyed bathymetry or a navigation chart. Demo boundaries now follow the demo-assets toggle in GIS as well as Live Monitoring.

Design references: [Rotterdam Weather & Tide](https://www.portofrotterdam.com/en/up-to-date-information/weather-tides-and-water-depth) and [Singapore MPA Maritime Digital Twin](https://www.mpa.gov.sg/maritime-singapore/innovation-and-r-d/maritime-digital-twin). The [OpenFreeMap source](https://openfreemap.org/quick_start/) supplies geographic context and its attribution; sensors still come from the existing connectors. No AIS, forecast, incident or operational dependency layer is introduced by this presentation change. `port_map.py` shares native layer presentation and encodes the application-owned style as a data URL for Streamlit 1.57 compatibility; no new dependency, API key or separate map-hosting service is required.

- **Shared context:** source-derived object IDs persist across the monitoring and object workspaces. Water charts, map state and quality inspection use the selected station, unit and vertical datum. Selected panels and layers survive deeper analysis.
- **Partner module intake:** Objects & Dependencies and Scenarios & Runs accept validated, data-only JSON handovers. Files are limited to 1 MB and ten run packages per session. Relationship assertions retain direction, validity, evidence and endpoint-alignment status. Run packages retain scenario/run IDs, model/input/ontology versions and provider evidence status. No upload executes code, calls its URLs or starts a model.
- **Explicit result comparison:** choose a current run and A/B runs yourself. Delta is B minus A only for matching entity, metric, unit and UTC valid time under the same declared ontology version. Unmatched values remain missing. Large integers retain exact table/CSV values; unsupported precise chart ranges are explained instead of silently rounded.
- **Accountable WP packages:** WP1 semantics/platform/metrics; WP2 data and monitoring; WP3 scenarios/models/runs; WP4 cross-sector dependencies and interoperability; WP5 security/ethics and integrated impact visualisation; WP6 four draft demonstrator task packages; WP7 governance handover records. These are prototype integration surfaces, not evidence that consortium research deliverables are complete.
- **Access and evidence:** the existing password gate remains before data loading. Partner selection still describes prototype navigation, not institutional authorisation. Locking the dashboard clears imported result packages. Imports remain in the current authorised Streamlit session and are not saved to the repository or server-side product storage. Provider validation and ontology labels remain declarations, not project acceptance. Formal WP1 alignment, verified operational dependencies, executable partner models and production governance controls remain pending.

Partner contracts and the minimum handover are documented in [docs/module-integration.md](docs/module-integration.md). The editable capability register is [data/wp_modules.json](data/wp_modules.json). The new code is split into `module_contracts.py` (registry and validated handovers), `workbench_data.py` (workspace identity and selection), and `workbench_views.py` (composable views). No new production dependency is required.

### Version 1 system overview (14 November 2026)

Overview now opens the main-page semantic demo. Use **Object type** and the object buttons, select **Map / Relations**, filter a **Relationship**, and follow related-object buttons in the inspector. The shared selection changes the available view profile and data products. **Content mode** and **Scenario** switch to illustrative impact/recovery outputs. The fixed **Demo period** defaults to 14 November 2026; changing it outside sample coverage returns unavailable products rather than zero values. The demo does not depend on live feeds or the current calendar date.

`semantic_service.py` queries RDF types, labels, relation instances, inverse labels and validity from `ontology/semantic_demo.ttl`. `data/semantic_demo.json` supplies type-to-view profiles, 20 synthetic products, two scenario contexts and non-executable model descriptors. `semantic_views.py` renders object navigation, map/graph picking, related-object jumps, product views and source/quality evidence. All demonstration objects and products use `demo:` identifiers. Coordinates are approximate and every source, relationship and numeric value is illustrative. The local draft is not the approved WP1 ontology, and relations do not trigger automatic impact propagation.

The **System overview** shortcut returns to Overview. **Monitor** opens **Live Monitoring**, with its original current/historical observation controls and source-derived object IDs. Demo selection and results do not replace live-object selection or imported partner packages. The previous **Integration Demo** teaching page and its implementation have been removed. Real partner result and dependency intake remains available through the existing model workspaces. No production dependency was added.

## Monitoring and Research Workspace

- **Monitoring** contains Overview (semantic demo), Live Monitoring, GIS, Observation Explorer, Transport and Data Quality. **Data & Research** holds Research & Replay, Report Centre and the original catalogue/status/raw-data views. Existing partner-view filters remain prototype navigation rules, not institutional access control.
- Live Monitoring supports selecting a gauge on the map; GIS also has a location selector as a WebGL fallback. Fresh/stale observations, traffic reference locations and demonstration assets remain distinct. A stale observation is not labelled absent, and neither data-health state implies flood severity.
- Observation Explorer filters one measurement reference and time interval, shows gaps and change rates, and exports the selected records. Rates are calculated only between consecutive 15-minute observations; no interpolation or datum conversion is applied. Plot zoom does not alter CSV export scope.
- Data Quality adds a prioritized review queue for stale, missing, invalid or unverifiable observations while preserving the full register, SOSA/SHACL checks and Turtle export.
- Research & Replay separates selected-gauge window inspection/animated history from archived experimental evidence, and follows Observation Explorer's partner-view restriction. An eight-point complete diagnostic window spans 105 minutes at a 15-minute cadence. Replay does not reconstruct the archived training samples, apply a model or produce warnings. Conflicting duplicates are withheld from diagnostics; raw report CSVs preserve source rows. Off-cadence observations remain visible rather than being discarded by plotting.
- Research charts reproduce `Summary_By_Group` and `PerFold_Metrics` from `16_final_context_physics_signature.xlsx`: eight feature families and 32 fold records. `data/research_provenance.json` records the source hash and metric definitions. Error bars are four-fold SD, not confidence intervals; false-positive windows are not alert episodes. The result tables do not change with the monitoring date selector.
- Report Centre exports a self-contained HTML snapshot, selected observation CSVs, quality/source registers and JSON metadata in one ZIP. Water references are charted separately; collection, observation and export times are explicitly distinguished.
- Feed requests are view-specific. Observation feeds have independent five-minute caches; statistical/reference feeds have one-day caches. Explorer and Replay request only water; Overview/GIS/Data Quality/Report Centre request water and traffic. The original full-feed pages still request all connected sources. The home feed count describes feeds retrieved by that view, not global service availability.

To rebuild the public aggregate research snapshot from the original workbook:

```powershell
.\.venv\Scripts\python scripts\extract_research_evidence.py C:\path\to\16_final_context_physics_signature.xlsx
```

The extractor validates summary means against per-fold rows. Full workbooks, row-level predictions, secrets and captured QA observations are not deployment inputs. No additional runtime dependency is required for this update. Streamlit is pinned to the locally verified 1.57.0 runtime so deployment does not depend on an older UI API; changing the dependency file also requests a fresh cloud build.

## Monitoring update (6 October 2026)

- Recent observations selects yesterday and today; historical browsing accepts a selected period of up to seven calendar days. EA water and WebTRIS traffic requests use the selected dates rather than a fixed 2024 traffic example.
- Overview separates current observation streams from connected APIs. Its coverage chart shows returned first/last timestamps, not uninterrupted coverage.
- GIS offers water-gauge, traffic-counter and optional demonstration-asset layers. The service-area outline remains a demonstration boundary.
- Weather displays one gauge/reference at a time, with UTC timestamps, a range slider and visible gaps. Temperature, wind and rain use independent axes. Local weather and transport examples remain explicitly labelled.
- Data Quality reports source age, missing intervals within the returned extent, duplicates, invalid times and values. Water freshness uses a 60-minute display budget; traffic uses 180 minutes only after timezone verification. Naive WebTRIS timestamps remain unverified and cannot be labelled current.
- Water datum metadata is read from individual EA measure definitions. Local datum identity can be derived from the measure's explicit link to its AOD counterpart. Unknown metadata remains unknown; there is no automatic datum conversion.
- `ontology/port_monitoring.ttl` declares a SOSA observation subclass. `ontology/observation_shapes.ttl` checks sensor, site, timestamp, result, unit and datum fields. RDFS class inference and SHACL validation do not establish flood risk or sensor accuracy.
- The live EA API normally retains about 28 days. Older historical replay requires archive ingestion. Official current warnings and published statistical tables retain their own time scope; they are not historical-event ground truth for a selected past period.

The demonstration weather/event timestamps have no documented timezone. Their original timestamps are preserved and are not treated as verified UTC observations. API credentials and `.streamlit/secrets.toml` must not be included in a release package.

## Verification

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python -m compileall -q app.py api_connectors.py data_quality.py monitoring_views.py
```

`scripts/preview_dashboard.py` is a local QA entry point using captured EA observations and saved historical tables. It is not the deployment entry point. Deploy `app.py`.

## Current scope

- Show the rank >= 4 data sources extracted from the CRDT available-datasets Word document.
- Visualise which high-score sources are already connected, which are reference-only, and which need credentials, partner permission, or GIS processing.
- Query open data through API or remote-file endpoints instead of manual download/upload.
- Display port/maritime, transport, GIS, weather sample, and water-level views.
- Include an Environment Agency Liverpool tide-gauge water-level connector.
- Keep the app simple enough for an early project demonstration.

## Main files

- `app.py`: Streamlit dashboard UI.
- `api_connectors.py`: API and remote-file connector layer.
- `data/high_score_dataset_catalog.csv`: rank >= 4 source catalogue extracted from the Word document.
- `data/partners.csv`: simple prototype partner selector and visible pages.
- `data/assets.csv`: minimal GIS point context for the demonstration.
- `data/service_area.geojson`: small service-area polygon.
- `data/weather_observations.csv`: small sample weather table.
- `data/transport_events.csv`: small sample transport table.
- `data/data_sources.csv`: local data-source register.
- `scripts/extract_docx_high_score_sources.py`: optional extraction script for the Word document.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Then open:

```text
http://127.0.0.1:8501/
```

The prototype dashboard asks for an access password before loading data or
showing the partner sidebar. Configure the password through Streamlit secrets
or an environment variable named `DASHBOARD_PASSWORD`.

For local development, create `.streamlit/secrets.toml`:

```toml
DASHBOARD_PASSWORD = "your-password"
```

The local secrets file is ignored by git. For Streamlit Community Cloud, add
the same `DASHBOARD_PASSWORD` entry in the app's Secrets settings, then reboot
or redeploy the app.

## Connected open-data sources

The dashboard currently connects to:

- Department for Transport port freight and ship-arrival tables.
- ONS weekly shipping indicators.
- Environment Agency monitoring stations and latest readings.
- Environment Agency Liverpool tide-gauge water levels.
- NaPTAN public transport access nodes.
- National Highways WebTRIS traffic site and daily report APIs.

Some high-score sources are intentionally listed as pending because they need credentials, partner permission, scraping review, or GIS clipping before they can be responsibly connected.

## Deployment note

This repository is suitable for GitHub and Streamlit Community Cloud as a prototype. For production deployment, add institutional authentication, server-side authorisation, audit logging, database-backed role policies, and reviewed data-sharing agreements.
