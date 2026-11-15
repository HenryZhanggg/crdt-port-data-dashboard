# Existing-data connections

15 November 2026, baseline `0959893`.

## Scope

Monitor → Connected observations → Connections now shows the selected water/traffic object's source, raw returned record set and measurement series, with evidence JSON download. Original EA station, measure and reading URIs are retained by the existing connector. Deduplication preserves distinct references and reading IDs as well as conflicting values. No request path, provider cache or dependency changed.

Graph identities are deterministic workspace references, pending project-wide semantic agreement. Traffic description matching and naive source time remain unverified; offset-aware times preserve their original offsets. Metric columns share one traffic record-set node. Returned traffic rows missing metric columns retain their record set and explain missing series.

Nearby candidates use supplied coordinates and a displayed 5 km Haversine rule. They are separate from partner-declared dependencies. Selecting one updates the existing inspector and releases incoming observation context. The existing GIS/source visibility guards, exact measurement/date handoffs, model-run comparisons and imported dependency filtering remain.

Overview / Monitor / Data and the existing engineering-monitoring theme are retained. This update does not ingest catalogue-only network layers or create operational/causal dependencies. Distributed WP adaptation responsibilities remain as documented in module-integration.md.

## Verification

- Full offline unittest suite: **266 tests passed**, 33.401 seconds. The final label/caption refinement was followed by the five relation-view tests, all passing. Connector regressions retain distinct original reading IDs, measure references and conflicting values.
- Local authenticated browser QA at 1600×1100 and 390×900 verified native graph rendering, original URI evidence, selected-reference JSON exports, water/traffic switching through a nearby candidate, two metric branches sharing one traffic snapshot, and the existing Data quality handoff/return. Different gauges/datums stayed separate.
- Settled desktop/mobile screenshots were visually inspected. Graph height is bounded; mobile pages have no horizontal document overflow. Shorter edge labels improve mobile legibility; uncertainty remains in node evidence, dashed links and a single visible mapping notice.
- Evidence is stored in the parent workspace's outputs/existing-data-connections-20261115, including full-tests.log, browser-verification.json, screenshots and downloaded JSON. Browser fixtures are local synthetic records, clearly labelled, and do not verify present provider availability. The deployment entry remains app.py.
- Code revision `403a842` was pushed without force to main. The sleeping Streamlit app was awakened through its public wake control; the deployed `Connected data relationships` marker, complete password field and Unlock dashboard button were then observed without a Streamlit exception. This online check covers the unauthenticated login surface; protected interactions were verified locally. Deployment evidence is in deployment-verification.json beside the local browser evidence.

Independent review identified deduplication of distinct reading IDs and a record-set omission when traffic metric columns are missing; both received regression fixes. Browser inspection identified excessive native graph height, corrected with a bounded chart height. Graph tooltips are bounded while full source evidence remains in the JSON export.
