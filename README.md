# CRDT port dashboard version 1

The application has three workspaces: **Overview**, **Monitor**, and **Data**. The sidebar keeps the prototype partner selector and session lock. The previous Workspace/View trees and standalone technical/project pages are retired.

[Open the Data integration workbench directly](https://crdt-port-data-dashboard.streamlit.app/?workspace=data&tool=integration&release=20261117b). Authentication and the selected partner view still apply. Data also has a prominent **Open integration workbench** button above its four tabs. Build `2026-11-17.2` appears after login and inside the Data/integration views; mismatched imported workspace builds are reloaded before use, or explicitly reported as an incomplete deployment.

## Overview

Daily Liverpool information: weather outlook, measured water levels, weather/flood reminders, a waterfront map, a dated Port/Weather/Travel update feed, and public site photos/video. Three summary cards and one weather/one water trend keep the main page compact; forecast and water records are available in collapsed details. Historical images and recorded film retain dates, source credits and licence terms. No live camera is asserted.

Each source shows its own check time or unavailable/link-only state. Forecast issue and valid times remain distinct from water observation times and age; water older than one hour is visibly marked late. Official notice/travel links lead the update feed, with weather/flood reminders before group news. Unknown warning validity remains unconfirmed.

Sources remain fixed and independently cached:

- MET Norway Locationforecast: forecasts, UTC valid times, three-hour Liverpool cache, CC BY 4.0 attribution. Expired forecast hours are filtered before display.
- EA Liverpool tide gauges: measured references remain separate by unit and vertical datum; missing/conflicting readings remain gaps. No predicted high/low tide times are connected.
- Met Office North West RSS and EA approximately 30km Liverpool-area flood query: fifteen-minute caches. Empty or unavailable feeds do not establish an all-clear or impacts on individual assets.
- Peel Ports Group news: dated headlines and original links, cached one hour; not exclusively Liverpool stories.
- Port marine notices and National Highways travel updates remain official links. Automatic current port-notice/road-incident feeds are not connected.

## Monitor

**Example network** uses the fixed local draft ontology and five fictional assets on 14 November 2026. Geographic category icons and directed predicates determine the selected object's Readings, Connections, Results and Sources. Search, types and relationship filters share one selection. Synthetic scenarios are selected inside Results. Example coordinates, relations and numeric products remain illustrative; formal WP1 alignment and executable partner models are pending.

**Connected observations** consolidates water and road traffic into a shared map and inspector. Select permitted source families, recent or historical dates (up to seven calendar days), then inspect Readings / Connections / Results / Sources. Water interval selection, change rates, CSV export and advanced observed replay preserve source units/datums and gaps. Traffic counter selection and optional comparisons retain unverified source timezone labels. No incident or port queue is inferred from a counter value.

Overview's **Explore readings** opens this view with the source station, unit, vertical datum and available UTC dates. **View data source** and **Check data quality** carry the selected reference/counter and dates into Data, including filtered CSV/report/Turtle exports. Returning preserves the selected reference; a missing requested series is explained without substituting another one. Users can clear the context or deliberately choose another object/source/date range. WebTRIS counts are historical and [usually published about one month after collection](https://webtris.highwaysengland.co.uk/Home/Faqs).

**Connections** shows a source → returned records → measurement series → selected object graph from the raw selected water/traffic response. Its JSON evidence retains source URIs, units/datums, original time basis and deterministic provisional workspace identities. Water measurements keep distinct properties, qualifiers and measure URIs; traffic metrics share one returned record set. WebTRIS report-to-counter description matching remains explicitly unverified. Nearby objects within 5 km are distance-only candidates that can be inspected, separate from the existing partner-declared dependency package. Catalogue-only OSM, rail and port asset layers are not asserted to be loaded or connected. No dependency or impact is inferred from proximity.

Published partner runs and declared dependency packages are inspected here after import in Data. Results use exact ontology-version/entity/metric/unit/UTC-valid-time matching for A/B comparison; unmatched outputs remain missing. Importing never runs a model. Source-derived workspace IDs are not approved canonical ontology identities. Refresh clears only the selected source/date cache entries and retains unrelated statistical and provider-limited weather caches.

## Data

- **Sources:** searchable catalogue with data-role and connector-route filters. The P0940-REP-103 C1 report (4 November 2026) is linked to fifteen of the sixteen catalogue entries, with PDF page references, useful tasks, limitations and follow-up checks; HS011 remains unmapped. Download the filtered register and curated evidence JSON. Report assessment, implemented connector and current retrieval status remain distinct. Choose a source, then enable Browse connected records to request available tables. DfT port freight/ship arrivals, ONS weekly shipping, EA stations/readings/water, WebTRIS counters and NaPTAN access nodes retain their routes. Preview tables show up to 200 rows; CSV exports include all returned rows.
- **Integration:** explicitly collect permitted water/traffic records for up to seven days, select exact measurement series, inspect draft common fields and configure a UTC decision cut-off and observation age. Collected mode uses recorded dashboard retrieval times, not historical provider publication times. Clearly labelled replay scenarios simulate delivery delays and missing records. Snapshot, decision audit, original raw-record evidence, request status and processing rules are downloadable as CSV/ZIP. Empty collections can export their check as JSON. Data collection is on demand and session-only; locking clears it. Formal WP1 alignment, model input acceptance and partner model execution remain for the responsible teams.
- **Quality:** scoped water/traffic checks, usability findings, compatibility and SOSA/SHACL structure checks; quality CSV, Turtle observation graph, and a self-contained observation report ZIP. Only requested source families are assessed. These checks do not establish physical accuracy, operating safety or accepted WP1 alignment.
- **Partner packages:** the only public JSON intake for model outputs and dependencies. Uploads are data-only, up to 1MB and ten run packages per session; URLs/code are not executed. Schema checks, duplicate run protection, exact integer handling and evidence declarations remain in place.
- **Project documents and research archive:** downloadable WP1–WP7 handovers, draft governance/demonstrator records, plus original scientific summary/folds/provenance and interpretation. They are supporting documents, separate from operational navigation. Observed replay stays in Monitor.

Traffic timestamps remain blocked unless offset-aware or accompanied by an explicitly recorded user assumption. Water measurement URIs, qualifiers, units and vertical datums remain separate. Invalid, missing, stale and conflicting input values remain missing rather than zero. Requests returning WebTRIS HTTP 204 retain counter metadata and an `api_no_data` status. A separate, dated [National Highways notice](https://webtris.highwaysengland.co.uk/Home/News) records the pause in new updates announced on 17 September 2026; this is not part of the November report assessment or a guarantee of coverage for selected historic counters.

Integration → **Upload CSV** accepts session-only UTF-8 observations (2 MB, 10,000 rows, 100 columns) with explicit entity/value/time mappings and metric/unit/reference declarations. Invalid rows remain auditable. Complete ISO date-times are required; time-only values and relative words do not acquire invented dates. Naive timestamps require an explicit timezone assumption. Original row numbers, content hash, source values, mapping and actual upload time accompany the canonical records. Uploading does not distribute the file to other partners or approve its ontology mapping.

After constructing a snapshot, **Build a model input table** lets the receiving team name input features, bind exact measurement series, confirm expected units and mark requirements. It exports one decision-time feature row, per-input checks and a JSON contract containing rules and source lineage. Stale/missing/conflicting or unit-mismatched values stay missing. Time assumptions need an explicit opt-in for the feature table; scientific model acceptance remains separate. Editor choices survive navigation; locking clears uploaded data and saved requirements.

The workflow and evidence boundaries are described in [docs/data-integration-workbench.md](docs/data-integration-workbench.md); report provenance is in [docs/data-validation-evidence.md](docs/data-validation-evidence.md).

Existing research evidence remains archived: eight feature families, 32 fold records, four-fold means/sample SD rather than confidence intervals, and false-positive windows rather than alert episodes. `research_provenance.json` records the source workbook hash. Changing dashboard dates does not change those archived experiments.

Partner handovers and distributed responsibilities are in [docs/module-integration.md](docs/module-integration.md). WP1 supplies common semantic guidance; WP2 supplies data access and validation; each consuming WP owns internal semantic adaptation and model-input construction. No new WP software ownership is assigned by this prototype.

## Run and access

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Deploy `app.py`. Local QA preview scripts are not deployment entry points. Configure `DASHBOARD_PASSWORD` in Streamlit Secrets or the environment; local `.streamlit/secrets.toml` is ignored by Git. The password gate precedes source retrieval. Partner selection is prototype navigation, not institutional server-side authorisation. Locking clears imported session packages.

Streamlit 1.57.0 and compatible Starlette 0.52.1 are pinned. The shared graphite/violet presentation lives in `dashboard_theme.py`; actual basemap geometry uses OpenFreeMap/OpenMapTiles/OpenStreetMap. Source coordinates are retained; screen label offsets only separate co-located references.

## Verify

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -q
```

Rebuild the scientific aggregate evidence with `scripts/extract_research_evidence.py` and the original workbook if needed. Raw workbooks, predictions, credentials and QA fixtures remain outside deployment inputs.
