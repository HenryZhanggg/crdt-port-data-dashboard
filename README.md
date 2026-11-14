# CRDT port dashboard version 1

Version 1 opens an everyday Liverpool overview: weather outlook, measured water levels, official weather/flood reminders, nearby travel links, Peel Ports Group headlines and saved places. The map is the main browsing entry. The dark interface separates everyday Overview from the geographic ontology-guided Monitor; other tools remain under More.

The default Overview uses fetched source data, never the semantic demonstration's synthetic values. **Overview** returns to it; **Monitor** opens the geographic connection network. **More → Observations** preserves the original observation workbench. Executable partner models and formal WP1 ontology alignment remain pending.

## Everyday overview (14 November 2026)

- **Weather:** [MET Norway Locationforecast](https://api.met.no/weatherapi/locationforecast/2.0/documentation), model forecasts with explicit valid/update times and [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) attribution. The Liverpool request is cached three hours under the provider's outside-Nordic guidance. Past cached hours are filtered again before display.
- **Tides & water:** existing EA Liverpool gauge observations, cached five minutes. References remain separate; missing/conflicting readings remain gaps. Predicted high/low tide times are not connected. Daily requests have a bounded retrieval budget.
- **Reminders:** Met Office North West RSS and the EA flood-warning location query, cached fifteen minutes. Empty and unavailable feeds differ. Regional weather and approximate 30km Liverpool flood results do not establish impacts on individual assets.
- **Port news:** dated [Peel Ports Group headlines](https://www.peelports.com/news-articles/), cached one hour, with original links. Stories can concern other ports; publication dates do not establish operational validity.
- **Port notices and travel:** [Peel Ports marine notices](https://www.peelports.com/marine/our-ports/liverpool/) and [National Highways](https://nationalhighways.co.uk/roads-and-travel/live-travel-updates/) are official source links. Automatic port-notice and road-incident feeds are not connected; links are not counted as live incidents.
- **My places:** up to four water references saved for the current authorized session, with selection isolated from the monitoring and example workspaces.

`daily_service.py` retrieves fixed sources and `daily_views.py` renders the homepage. Source publication, observation/forecast valid time and retrieval time remain separate. Source loading follows the password gate. Observations refresh clears its observation/reference caches without evicting the provider-limited weather cache.

### Public site imagery and film

Overview includes **From the waterfront → Photos / Video**. Two reduced-resolution Seaforth photographs are stored locally with original source pages, capture dates, author credits and CC BY-SA 4.0 terms in `data/public_media.json`. These are historical site images, not current operating evidence. The official Peel Ports film uses its verified YouTube player only after selecting Video, without autoplay; film copyright stays with its publisher and its official page remains available if playback is restricted. No live camera has been connected.

The shared `dashboard_theme.py` applies the graphite/violet theme across native controls, charts and maps. Streamlit 1.57 and its compatible Starlette 0.52.1 media adapter are pinned and verified by the media-response regression test.

## Modular port workbench (13 November 2026)

Live Monitoring combines a map, a shared water/traffic/illustrative-asset inspector and selectable panels. Use the top shortcuts for monitoring, objects/dependencies, scenario results, data/evidence and WP handovers; the sidebar retains all existing observation, transport, quality, research/replay, catalogue and report views. The shared observation dates retain their original seven-calendar-day limit. Map colours describe data state, not hazard severity. Demonstration assets and the service-area outline are opt-in.

The 14 November interface refresh adds a compact navy header, time/date/refresh toolbar, source-reference metadata and consistent neutral panels/charts. Existing summary metrics sit above the map; the selected-observation chart sits directly below it. Expand **Workspace panels** to change the optional panels. On narrow screens, the map and trend stack before the object inspector. **Recent observations** requests yesterday and today with cached responses; refresh is manual, not continuous polling.

The maritime-map update uses an authored navy OpenFreeMap basemap in both Live Monitoring and GIS. Muted green marks current water data, purple other water states, blue traffic and grey illustrative assets. Pickable labels separate co-located objects using screen-pixel offsets without changing their source coordinates. Live Monitoring adds a violet selection ring and selected-label border linked to the inspector. Native map selection resets when visible membership or the manual object choice changes; this also resets the camera, avoiding stale row-index selection. The map shows geographic context, not surveyed bathymetry or a navigation chart. Demo boundaries now follow the demo-assets toggle in GIS as well as Live Monitoring.

Design references: [Rotterdam Weather & Tide](https://www.portofrotterdam.com/en/up-to-date-information/weather-tides-and-water-depth) and [Singapore MPA Maritime Digital Twin](https://www.mpa.gov.sg/maritime-singapore/innovation-and-r-d/maritime-digital-twin). The [OpenFreeMap source](https://openfreemap.org/quick_start/) supplies geographic context and its attribution; sensors still come from the existing connectors. No AIS, forecast, incident or operational dependency layer is introduced by this presentation change. `port_map.py` shares native layer presentation and encodes the application-owned style as a data URL for Streamlit 1.57 compatibility; no new dependency, API key or separate map-hosting service is required.

- **Shared context:** source-derived object IDs persist across the monitoring and object workspaces. Water charts, map state and quality inspection use the selected station, unit and vertical datum. Selected panels and layers survive deeper analysis.
- **Partner module intake:** Objects & Dependencies and Scenarios & Runs accept validated, data-only JSON handovers. Files are limited to 1 MB and ten run packages per session. Relationship assertions retain direction, validity, evidence and endpoint-alignment status. Run packages retain scenario/run IDs, model/input/ontology versions and provider evidence status. No upload executes code, calls its URLs or starts a model.
- **Explicit result comparison:** choose a current run and A/B runs yourself. Delta is B minus A only for matching entity, metric, unit and UTC valid time under the same declared ontology version. Unmatched values remain missing. Large integers retain exact table/CSV values; unsupported precise chart ranges are explained instead of silently rounded.
- **Accountable WP packages:** WP1 semantics/platform/metrics; WP2 data and monitoring; WP3 scenarios/models/runs; WP4 cross-sector dependencies and interoperability; WP5 security/ethics and integrated impact visualisation; WP6 four draft demonstrator task packages; WP7 governance handover records. These are prototype integration surfaces, not evidence that consortium research deliverables are complete.
- **Access and evidence:** the existing password gate remains before data loading. Partner selection still describes prototype navigation, not institutional authorisation. Locking the dashboard clears imported result packages. Imports remain in the current authorised Streamlit session and are not saved to the repository or server-side product storage. Provider validation and ontology labels remain declarations, not project acceptance. Formal WP1 alignment, verified operational dependencies, executable partner models and production governance controls remain pending.

Partner contracts and the minimum handover are documented in [docs/module-integration.md](docs/module-integration.md). The editable capability register is [data/wp_modules.json](data/wp_modules.json). The new code is split into `module_contracts.py` (registry and validated handovers), `workbench_data.py` (workspace identity and selection), and `workbench_views.py` (composable views). No new production dependency is required.

### Geographic Monitor (14 November 2026)

Open **Monitor → Example network** for the semantic demonstration. Category icons sit at approximate geographic coordinates; arrows preserve each declared predicate direction. **Available observations** is a separate gauge-only mode with source references and readings; no dependency edges are inferred. Use **Object type** and the object buttons, select **Map / Relations**, filter a **Relationship**, and follow related-object buttons in the inspector. The shared selection changes the available view profile and data products. **Content mode** and **Scenario** switch to illustrative impact/recovery outputs. The fixed **Demo period** defaults to 14 November 2026; changing it outside sample coverage returns unavailable products rather than zero values. The example does not depend on live feeds or the current calendar date.

`semantic_service.py` queries RDF types, labels, relation instances, inverse labels and validity from `ontology/semantic_demo.ttl`. `data/semantic_demo.json` supplies type-to-view profiles, 20 synthetic products, two scenario contexts and non-executable model descriptors. `semantic_views.py` renders object navigation, map/graph picking, related-object jumps, product views and source/quality evidence. All demonstration objects and products use `demo:` identifiers. Coordinates are approximate and every source, relationship and numeric value is illustrative. The local draft is not the approved WP1 ontology, and relations do not trigger automatic impact propagation.

The **Overview** shortcut returns to the everyday homepage. **More → Observations** opens the original observation controls and source-derived IDs. Example selection and results do not replace live-object selection or imported partner packages. The previous **Integration Demo** teaching page remains removed. Real partner intake is available through More and the sidebar. No production dependency was added.

## Monitoring and Research Workspace

- **Monitoring** contains Overview (everyday homepage), Monitor (network), Observations (internally Live Monitoring), GIS, Observation Explorer, Transport and Data Quality. **Data & Research** holds Research & Replay, Report Centre and the original catalogue/status/raw-data views. Existing partner-view filters remain prototype navigation rules, not institutional access control.
- Live Monitoring supports selecting a gauge on the map; GIS also has a location selector as a WebGL fallback. Fresh/stale observations, traffic reference locations and demonstration assets remain distinct. A stale observation is not labelled absent, and neither data-health state implies flood severity.
- Observation Explorer filters one measurement reference and time interval, shows gaps and change rates, and exports the selected records. Rates are calculated only between consecutive 15-minute observations; no interpolation or datum conversion is applied. Plot zoom does not alter CSV export scope.
- Data Quality adds a prioritized review queue for stale, missing, invalid or unverifiable observations while preserving the full register, SOSA/SHACL checks and Turtle export.
- Research & Replay separates selected-gauge window inspection/animated history from archived experimental evidence, and follows Observation Explorer's partner-view restriction. An eight-point complete diagnostic window spans 105 minutes at a 15-minute cadence. Replay does not reconstruct the archived training samples, apply a model or produce warnings. Conflicting duplicates are withheld from diagnostics; raw report CSVs preserve source rows. Off-cadence observations remain visible rather than being discarded by plotting.
- Research charts reproduce `Summary_By_Group` and `PerFold_Metrics` from `16_final_context_physics_signature.xlsx`: eight feature families and 32 fold records. `data/research_provenance.json` records the source hash and metric definitions. Error bars are four-fold SD, not confidence intervals; false-positive windows are not alert episodes. The result tables do not change with the monitoring date selector.
- Report Centre exports a self-contained HTML snapshot, selected observation CSVs, quality/source registers and JSON metadata in one ZIP. Water references are charted separately; collection, observation and export times are explicitly distinguished.
- Feed requests are view-specific. Explorer and Replay request water; Live Monitoring/GIS/Data Quality/Report Centre request water and traffic. Observation caches are five minutes; statistical/reference caches are one day. Overview uses the separately cached daily sources above. Monitor / Example network uses local illustrative fixtures; Available observations reuses the daily source snapshot and displays only real gauge references and readings. Counts describe the requested sources, not global availability.

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
