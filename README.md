# CRDT-Port Data Visualisation Dashboard

This repository contains a lightweight Streamlit demonstrator for the CRDT-Port project. The current version focuses on data display and visualisation only. It does not implement resilience scoring, ontology integration, production authentication, or automated decision workflows.

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
