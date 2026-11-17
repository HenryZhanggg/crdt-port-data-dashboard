# Data validation and integration workbench implementation plan

> **For agentic workers:** Execute the approved work in this existing isolated dashboard checkout, with bounded file ownership and independent review before release.

**Goal:** Turn the Data workspace into a usable source-validation register and historical/updated-observation integration workbench, grounded in the latest project report and actual returned records.

**Architecture:** Keep Overview / Monitor / Data and existing lazy source retrieval. Add page-referenced report evidence to Sources, a separate lazy Integration tab using pure pandas processing, and reproducible CSV/ZIP exports. Existing Quality checks, exact observation handoffs, partner packages and access gates remain intact.

**Tech stack:** Existing Streamlit, pandas, Plotly and standard-library ZIP/JSON. No dependency, hosted database, scheduled collector, arbitrary endpoint or model execution is introduced.

## Approved design and scope

The user approved the preceding plan and explicitly requested implementation and dashboard updates. Implement now without another approval checkpoint. Report findings describe the report's assessment, while runtime source status describes a specific retrieval. Connector presence does not establish present access, completeness or suitability for a model.

### Task 1: Report-grounded source register

- [x] Read P0940-REP-103 C1, issued 4 November 2026; extract high-level findings with PDF page references, report hash and explicit assessment status.
- [x] Align all sixteen existing catalogue IDs; sources without a confirmed report mapping remain unmapped.
- [x] Add search/filter controls, temporal-role and connector columns, source-specific findings, follow-up checks and downloadable register/evidence.
- [x] Verify report page bounds, ID coverage and AppTest lazy retrieval/metadata navigation.

Files: `data/validation_report.json`, `validation_views.py`, `data_views.py`, `tests/test_validation_report.py`, `tests/test_validation_views.py`.

### Task 2: Interactive historical/updated-observation integration

- [x] Test normalization, reference separation, timestamps, duplicates/conflicts, no-lookahead snapshots, stale/unknown states and explicitly simulated replay before implementation.
- [x] Preserve raw evidence and separate dashboard retrieval time from unavailable historical publication/receipt time.
- [x] Add explicit source/date retrieval, series selection, cutoff/freshness controls, traffic timezone assumptions and replay delay/missingness controls.
- [x] Display normalized records, semantic mapping fields, snapshot values/statuses and exclusion audit; export CSV and a reproducible ZIP including processing rules.
- [x] Retain exact incoming observation context and recheck permissions for retained session data.

Files: `data_integration.py`, `integration_views.py`, `tests/test_data_integration.py`, `tests/test_integration_views.py`.

### Task 3: Integration, QA and release

- [x] Wire the lazy Integration tab, widget preservation and clearing of collected session data on lock.
- [x] Run focused tests and the full offline suite; independently review report claims and time/reference correctness.
- [x] Exercise Data sources, report filters, collection, replay, exports and existing handoffs in desktop/mobile browsers. Verify no Streamlit exceptions or document overflow.
- [x] Probe selected public sources without representing errors as absence; record observed access/coverage and actual verification times.
- [ ] Update README, handover notes and visible release marker; commit only task files and push without force to the existing deployment branch after verification.
- [ ] Observe the deployed release marker and login surface; distinguish protected local QA from online access verification.

## Acceptance boundaries

Replay receipt times and interruptions are scenarios, never measured provider latency. WebTRIS is historical and naive timestamps remain unverified unless a user explicitly supplies a recorded assumption. Water units/datums/measure references are not merged. Missing or conflicting outputs are not filled with zero. The workbench builds inspectable data inputs, without claiming scientific model acceptance, an approved WP1 ontology or completed partner-model synchronization. Continuous unattended capture and durable shared storage need separately agreed infrastructure; session snapshots and exports are labelled accordingly.
