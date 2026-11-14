# Three workspaces implementation plan

> For agentic workers: use subagent-driven-development with separate file ownership and requirements/quality review. The user approved the proposed simplification and instructed implementation.

**Goal:** Replace 17 public views with Overview, Monitor and Data while preserving unique data/validation/integration capabilities.

**Architecture:** Keep existing connectors, quality rules, product contracts, source evidence and cache boundaries. Overview is a compact daily home. Monitor owns geography, selected-object observations/relations/results and historical inspection; examples stay separate from real sources. Data owns catalogue/previews, detailed quality, partner intake and exports. Project handovers and scientific results become downloadable archives, not operational pages.

**Tech stack:** Existing Streamlit 1.57, Pydeck, Plotly, pandas, rdflib/pyshacl; no new dependencies.

## Task 1 — Compact Overview

Files: daily_views.py, tests/test_daily_views.py.

- [x] Remove My places and the non-reading Port notices metric; retain official notice links in the unified update feed.
- [x] Keep one weather and one water mini trend, map, source-dated update feed, and historical photo/video panel. Replace duplicate bottom Weather/Water/Travel/News tabs with compact weather/water record details and existing attribution.
- [x] Verify no lost datum, timestamp, forecast attribution, failure/empty-feed distinction or map-selection behavior.

## Task 2 — One Monitor workspace

Files: monitor_workspace.py (new), semantic_views.py, workbench_views.py as required, monitoring_views.py as required, monitor/semantic/workbench/dashboard tests.

- [x] Explicit Example network / Connected observations modes; example mode uses fixed date caption, geographic map only, no disabled model cards, duplicate scenario button or circular graph.
- [x] Real mode consolidates water/traffic map and inspector, source-quality status, historical date selection, selected Readings/Connections/Results/Sources, range/CSV/changes/replay and optional traffic comparison.
- [x] Preserve imported dependency evidence and published-run A/B comparisons; one intake lives in Data. No inferred real links or model execution. Empty outputs use compact messages, not empty placeholder panels.
- [x] Add meaningful regressions for shared selection, source isolation, filtered records/exports, dates, arrows, gaps and data-package results.

## Task 3 — Data workspace and routing

Files: data_views.py (new), app.py, navigation helper if needed, routing/data tests.

- [x] Only three top-level buttons; sidebar keeps session/partner controls without Workspace/View trees. Safely migrate old state to its new workspace/context.
- [x] Data source catalogue/search/select then source details and available table previews. Preserve DfT port/arrivals, ONS shipping, EA, tide, WebTRIS and NaPTAN; fetch selected families only.
- [x] Data quality queue, detailed compatibility/SOSA/SHACL/Turtle and one partner JSON intake. Existing CSV and self-contained HTML+CSV+quality ZIP export remain usable.
- [x] Put observation dates only where observations/reports require them; refresh specific caches and preserve MET three-hour policy. Partner intake and static archives must not request feeds.
- [x] Download WP handovers/governance/demonstrator drafts and research summary/folds/provenance from a small archive expander; remove their standalone public pages without deleting source evidence.

## Task 4 — Integration, review and deploy

Files: dashboard_theme.py only if new container styles need them, README.md, docs/module-integration.md, focused verification note.

- [x] Run unittest suite from .venv/Scripts/python.exe; replace obsolete navigation assertions with capability-preserving checks rather than dropping coverage.
- [x] Browser verify default daily home, native map/selection, water and traffic history, run import/comparison, Data source previews and exports, archived downloads, lazy media, and readable 390px layout.
- [x] Independent requirements then code-quality review; fix material findings.
- [x] Verify remote main remains compatible with baseline aa0b7d9, non-force push to Streamlit's main branch, observe updated version marker and completed login form. Protected online interactions require credentials; local authenticated QA remains distinct.

## Explicit preservation rules

No changes to funding monitoring or research source files outside this dashboard. Preserve unrelated untracked visual-navigation-layout.md. No external contacts. Source time/unit/datum and missing-vs-zero semantics remain intact. Source-derived identifiers do not become approved ontology IDs. Uploaded packages remain data only and session local; no calls to uploaded URLs or model code.

Release code bc41983 was pushed without force to main. The remote Overview / Monitor / Data version marker and complete password form were observed on 14 November 2026; protected interactions were verified locally.
