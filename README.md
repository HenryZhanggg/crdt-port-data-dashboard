# CRDT-Port Data Visualisation Dashboard

This repository contains a Streamlit monitoring demonstrator for the CRDT-Port project. It displays observations, source coverage and data-quality evidence, and maps water observations into a small SOSA ontology validated with SHACL. It does not yet run pre-warning model inference, asset-impact reasoning or production authentication.

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
