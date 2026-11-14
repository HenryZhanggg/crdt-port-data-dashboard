# Port launch theme, network monitor and public media implementation plan

> For agentic workers: use subagent-driven development for independent ownership and review; the user approved the design in chat and added public site imagery/video.

**Goal:** Deliver the approved minimalist Overview / Monitor product on the existing Streamlit deployment, including licensed Liverpool site media.

**Architecture:** Keep the existing daily source service and fixed semantic package. Overview consumes current weather/water/updates plus a small curated public-media manifest. Monitor renders the draft-ontology example as a geographic directed network and offers an explicitly separate available-observation mode. Preserve all data/model/WP tools under More. No model execution or invented live asset dependencies.

**Tech stack:** Existing Streamlit 1.57, Pydeck, Plotly, pandas, fixed local JSON/media; no new runtime dependencies.

## Approved visual and evidence requirements

- Graphite #080B12 background, #111722 panels, #253041 dividers, #F2F5F9 text, #95A2B5 secondary text and #7C83FD selected elements. Status colors only convey actual evidence states.
- Main navigation Overview / Monitor / More; More retains Observations, data, model and WP pages. Migrate existing session routes.
- Overview: four compact daily cards, map around 65% and dated/source-linked update feed around 35%, weather/water summaries, licensed site imagery/video and details below. No ontology jargon on the daily home.
- Monitor: asset register, geographic network with category symbols and directional predicates, selected-asset inspector, readings/connections/scenario/source details. Highlight one-hop edges and mute unrelated links. Actual observed data and illustrative network remain separate modes.
- Public media must have verified original page, file URL, credit, license and capture date when supplied. Historical media is visibly historical. Do not invent or label an unverified live camera feed. A small local preview prevents remote hotlink failures; videos are user-initiated, not autoplay.
- Keep the exact product name CRDT port dashboard version 1 and preserve authentication.

## Task 1 — Media verification (read-only research)

- [x] Find geographically relevant Commons or official public media and verify license/source/date directly.
- [x] Record original URLs and limitations in the release evidence folder. Prefer 2–4 photos and one playable video; do not substitute a generic port.

## Task 2 — Geographic Monitor

Files: semantic_views.py, a small network-map helper if needed, tests/test_semantic_views.py and focused network tests.

- [x] Build geographic category-icon nodes and explicit directional edges from existing semantic package only.
- [x] Provide asset search/type/relation filtering, native node selection with reset handling, edge evidence, and observations/example modes without mixing datasets.
- [x] Preserve synthetic sample results and disabled unconnected model actions. Pass existing behavioral tests or update intentionally changed UI expectations.

## Task 3 — Theme and navigation

Files: app.py, workbench_views.py, monitoring_views.py, port_map.py, .streamlit/config.toml, tests/test_daily_routing.py.

- [x] Replace obsolete light theme styling at its source and apply consistent native dark widgets, chart colors and low-saturation map.
- [x] Route Overview and network Monitor directly; keep real workbench as More / Observations and migrate previous routes.
- [x] Verify authentication, targeted refresh cache retention and secondary-page navigation.

## Task 4 — Overview and public media

Files: daily_views.py, a small public-media JSON and local previews, tests/test_daily_views.py plus focused manifest checks.

- [x] Unified date-sorted, categorized update feed retaining missing-source messages and links.
- [x] Compact weather/water trends and source details; retain reference selection and saved places.
- [x] Add photographs and video with visible capture date/license/source and explicit historical context. No autoplay or remote feed scraping.

## Task 5 — Verify, review and deploy

- [x] Run .venv/Scripts/python.exe -m unittest discover -s tests -q and inspect all failures.
- [x] Run local authenticated preview with fixture and captured actual source data; inspect screenshots, native map selections, navigation, video load and mobile overflow.
- [x] Independent spec then quality review; fix material findings and rerun affected checks.
- [x] Check remote main against baseline before non-force push HEAD:main; preserve unrelated untracked plan.
- [x] Observe deployed version marker and completed login form. Report authenticated local versus unauthenticated online validation accurately.

Release code 617c3ed was pushed without force to main. The deployed new version marker and completed password form were observed on 14 November 2026; protected interactions were verified locally.
