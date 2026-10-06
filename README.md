# CRDT-Port Data Visualisation Dashboard

This repository contains a Streamlit monitoring demonstrator for the CRDT-Port project. It displays observations, source coverage and data-quality evidence, and maps water observations into a small SOSA ontology validated with SHACL. It does not yet run pre-warning model inference, asset-impact reasoning or production authentication.

## Monitoring and Research Workspace

- **Monitoring** is the home section: Overview, GIS, Observation Explorer, Transport and Data Quality. **Data & Research** holds Research & Replay, Report Centre and the original catalogue/status/raw-data views. Existing partner-view filters remain prototype navigation rules, not institutional access control.
- The map-led overview supports selecting a gauge on the map; GIS also has a location selector as a WebGL fallback. Fresh/stale observations, traffic reference locations and demonstration assets remain distinct. A stale observation is not labelled absent, and neither data-health state implies flood severity.
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

- Live monitoring selects yesterday and today; historical browsing accepts a selected period of up to seven calendar days. EA water and WebTRIS traffic requests use the selected dates rather than a fixed 2024 traffic example.
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
